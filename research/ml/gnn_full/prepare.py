"""Disk-backed full-inventory extraction, global Event dedup and temporal graphs."""
from __future__ import annotations
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import time
import subprocess
import sys
import uuid
import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from fastavro import reader
from research.ml.data_prep.resolve_references import clean, reusable_files
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash
from research.ml.node_benchmark.build_graphs import iso_nanos

WINDOW=300_000_000_000
TRAIN_END=iso_nanos('2019-05-09T00:00:00Z')
DEV_END=iso_nanos('2019-05-10T00:00:00Z')
SCHEMA=pa.schema([(n,pa.binary(16)) for n in ('host','event','actor','obj1','obj2')]+[
    ('ts',pa.int64()),('action',pa.int16()),('source',pa.int16()),('ordinal',pa.int32()),('fp',pa.binary(32))])


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_bytes((json.dumps(value,indent=2,allow_nan=False)+'\n').encode());temp.replace(path)


def uid(value):
    if value is None:return None
    try: result=value if isinstance(value,bytes) else uuid.UUID(str(value)).bytes
    except (ValueError,TypeError,AttributeError):return None
    return result if len(result)==16 and any(result) else None


def role(window):
    if window<TRAIN_END:return 'train'
    if TRAIN_END+WINDOW<=window<DEV_END:return 'development'
    if window>=DEV_END+WINDOW:return 'test'
    return 'purge'


def disk_guard(work,minimum=8*1024**3):
    if shutil.disk_usage(work).free<minimum:raise RuntimeError('Insufficient free disk; stopping without reducing source coverage')


def connect(work):
    con=duckdb.connect(str(work/'dedup.duckdb'))
    con.execute("SET memory_limit='3GiB'");con.execute('SET threads=10')
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='"+str(work/'duck-temp').replace("'","''").replace('\\','/')+"'")
    scratch=max(1,min(65,int((shutil.disk_usage(work).free/1024**3-12)/2)))
    con.execute(f"SET max_temp_directory_size='{scratch}GiB'")
    return con


def extract_serial(source,audit,work,actions,only_index=None):
    paths=list(source.rglob('*.gz')); files=reusable_files(paths,audit)
    if len(paths)!=len(files) or len({p.name for p in paths})!=len(files):raise ValueError('Source inventory differs from complete audit')
    files=sorted(files,key=lambda f:f['filename']); by={p.name:p for p in paths}
    work.mkdir(parents=True,exist_ok=True);(work/'staged').mkdir(exist_ok=True)
    index={name:i for i,name in enumerate(actions)}
    completed=[]
    for number,item in enumerate(files):
        if only_index is not None and number!=only_index:continue
        target=work/'staged'/f'{number:03d}.parquet';receipt=work/'staged'/f'{number:03d}.json'
        if receipt.exists():
            previous=json.loads(receipt.read_text(encoding='utf-8'))
            if previous['source']!=item or file_hash(target)!=previous['parquet_sha256']:raise ValueError('Changed extraction receipt')
            completed.append(previous);continue
        if target.exists():raise ValueError('Unreceipted extraction output; inspect interrupted file before resuming: '+str(target))
        disk_guard(work);started=time.perf_counter();counts=Counter();excluded=Counter();rows=[];events=0;records=0
        writer=pq.ParquetWriter(target,SCHEMA,compression='zstd',use_dictionary=['host','actor','obj1','obj2','action','source'])
        try:
            with gzip.open(by[item['filename']],'rb') as stream:
                for records,raw in enumerate(reader(stream),1):
                    kind=raw.get('type');counts[kind]+=1
                    if kind=='RECORD_EVENT':
                        datum=raw.get('datum');datum=datum[1] if isinstance(datum,tuple) else datum
                        host,event,actor=uid(raw.get('hostId')),uid(datum.get('uuid')),uid(datum.get('subject'))
                        ts=datum.get('timestampNanos')
                        if host is None or event is None or actor is None or type(ts) is not int or not 0<=ts<2**63:
                            excluded['invalid_host_event_actor_or_timestamp']+=1
                        elif any(datum.get(key) is not None and uid(datum[key]) is None for key in ('predicateObject','predicateObject2')):
                            excluded['invalid_present_predicate_identifier']+=1
                        else:
                            fingerprint=hashlib.sha256(json.dumps(clean(raw),sort_keys=True,separators=(',',':')).encode()).digest()
                            rows.append(dict(host=host,event=event,actor=actor,obj1=uid(datum.get('predicateObject')),
                                obj2=uid(datum.get('predicateObject2')),ts=ts,action=index.get(datum.get('type'),len(actions)),
                                source=number,ordinal=records,fp=fingerprint));events+=1
                            if len(rows)>=100_000:
                                disk_guard(work);writer.write_table(pa.Table.from_pylist(rows,schema=SCHEMA));rows=[]
                    if records%250_000==0:
                        progress=dict(phase='extracting',source=number+1,total_sources=len(files),filename=item['filename'],
                            records_in_source=records,previous_complete_sources=len(completed),elapsed_source_seconds=time.perf_counter()-started)
                        save(work/(f'source_progress_{number:03d}.json' if only_index is not None else 'progress.json'),progress);print(json.dumps(progress),flush=True)
            if rows:writer.write_table(pa.Table.from_pylist(rows,schema=SCHEMA))
        finally:writer.close()
        stat=by[item['filename']].stat()
        if records!=item['records'] or dict(counts)!=item['record_type_counts'] or (stat.st_size,stat.st_mtime_ns)!=(item['compressed_bytes'],item['modified_time_ns']):
            raise ValueError('Source changed or full decoded counts disagree: '+item['filename'])
        result=dict(source=item,records=records,eligible_event_occurrences=events,excluded=dict(excluded),
            gzip_exhaustion_verified=True,parquet_sha256=file_hash(target),parquet_bytes=target.stat().st_size,
            compressed_source_sha256=file_hash(by[item['filename']]),elapsed_seconds=time.perf_counter()-started)
        save(receipt,result);completed.append(result)
    if only_index is not None:return completed
    save(work/'extraction.json',dict(status='all_sources_extracted',source_count=len(files),
        reference_audit_sha256_utf8_lf=text_hash(audit/'reference_report.json'),sources=completed))
    return completed



def extract(source,audit,work,actions,workers=4):
    paths=list(source.rglob('*.gz'));files=sorted(reusable_files(paths,audit),key=lambda f:f['filename'])
    if len(paths)!=len(files) or len({p.name for p in paths})!=len(files):raise ValueError('Raw inventory differs')
    work.mkdir(parents=True,exist_ok=True);(work/'staged').mkdir(exist_ok=True)
    save(work/'actions.json',actions)
    pending=[];completed=[];active={}
    for number,item in enumerate(files):
        receipt=work/'staged'/f'{number:03d}.json';target=receipt.with_suffix('.parquet')
        if receipt.exists():
            previous=json.loads(receipt.read_text(encoding='utf-8'))
            if previous['source']!=item or file_hash(target)!=previous['parquet_sha256']:raise ValueError('Completed source changed')
            completed.append(previous)
        else:pending.append(number)
    try:
        while pending or active:
            disk_guard(work)
            while pending and len(active)<workers:
                number=pending.pop(0)
                command=[sys.executable,'-u','-m','research.ml.gnn_full.extract_worker',
                    '--source',str(source),'--audit',str(audit),'--work',str(work),'--index',str(number)]
                active[number]=subprocess.Popen(command)
            for number,process in list(active.items()):
                code=process.poll()
                if code is not None:
                    if code!=0:raise RuntimeError(f'Archive worker {number} failed with exit code {code}')
                    receipt=work/'staged'/f'{number:03d}.json'
                    result=json.loads(receipt.read_text(encoding='utf-8'))
                    if result['source']!=files[number]:raise ValueError('Parallel source receipt differs')
                    completed.append(result);del active[number]
            progress=dict(phase='extracting_parallel',cpu_workers=workers,active_workers=len(active),
                active_sources=[files[i]['filename'] for i in active],
                verified_complete_sources=len(completed),total_sources=len(files),
                verified_complete_records=sum(r['records'] for r in completed))
            current={}
            for number in active:
                path=work/f'source_progress_{number:03d}.json'
                if path.exists():current[files[number]['filename']]=json.loads(path.read_text(encoding='utf-8'))['records_in_source']
            progress['active_source_record_counts']=current
            save(work/'progress.json',progress)
            print(json.dumps(progress),flush=True)
            save(work/'workers.json',{str(i):p.pid for i,p in active.items()})
            if active:time.sleep(3)
    except BaseException:
        for process in active.values():
            if process.poll() is None:process.terminate()
        for process in active.values():process.wait()
        raise
    completed.sort(key=lambda r:r['source']['filename'])
    save(work/'extraction.json',dict(status='all_sources_extracted',source_count=len(files),
        reference_audit_sha256_utf8_lf=text_hash(audit/'reference_report.json'),sources=completed))
    return completed


def deduplicate(work):
    done=work/'deduplication.json'
    if done.exists():return json.loads(done.read_text(encoding='utf-8'))
    disk_guard(work);save(work/'progress.json',dict(phase='global_deduplication'))
    with connect(work) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS event_groups AS
            SELECT host,event,min(fp) first_fp,max(fp) last_fp,count(*) occurrences,
            arg_min(struct_pack(actor:=actor,obj1:=obj1,obj2:=obj2,ts:=ts,action:=action,source:=source,ordinal:=ordinal),
                    struct_pack(source:=source,ordinal:=ordinal)) payload
            FROM read_parquet(?) GROUP BY host,event''',[str(work/'staged'/'*.parquet')])
        occurrences,unique,conflicts,repeats=con.execute('''SELECT sum(occurrences),count(*),
            count(*) FILTER(WHERE first_fp<>last_fp),
            coalesce(sum(occurrences-1) FILTER(WHERE first_fp=last_fp),0) FROM event_groups''').fetchone()
        target=work/'buckets'
        if target.exists():raise ValueError('Incomplete temporal export exists; inspect before resuming')
        con.execute('''COPY (SELECT host,event,payload.actor actor,payload.obj1 obj1,payload.obj2 obj2,
            payload.ts ts,payload.action action,payload.source source,payload.ordinal ordinal,
            (payload.ts // 300000000000)*300000000000 AS "window",lower(hex(host)) host_key
            FROM event_groups WHERE first_fp=last_fp) TO ?
            (FORMAT PARQUET,PARTITION_BY(host_key,"window"),COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)''',[str(target)])
        result=dict(status='global_deduplication_complete',eligible_raw_event_occurrences=occurrences,
            unique_event_keys=unique,conflicting_event_keys_quarantined=conflicts,identical_repeats_removed=repeats,
            unique_usable_events=unique-conflicts,policy='Native (host,Event UUID), full canonical raw-record SHA256; quarantine all conflicting keys')
    save(done,result)
    # Only derived, fully receipted staging files within this approved work folder.
    # Durable global groups and verified extraction receipts remain for auditing.
    staged=(work/'staged').resolve(); root=work.resolve()
    if staged.parent!=root:raise ValueError('Unsafe derived-staging cleanup path')
    for path in staged.glob('*.parquet'):
        receipt=path.with_suffix('.json')
        if not receipt.exists():raise ValueError('Cannot clean an unreceipted derived file')
        if file_hash(path)!=json.loads(receipt.read_text(encoding='utf-8'))['parquet_sha256']:raise ValueError('Derived staging changed')
        path.unlink()
    return result


def graph_arrays(table,action_count):
    def column(name):return table[name].to_pylist()
    actors=column('actor'); one=column('obj1');two=column('obj2')
    actions=np.asarray(column('action'),dtype=np.int64)
    ids=np.frombuffer(b''.join(actors+[v for v in one if v is not None]+[v for v in two if v is not None]),dtype='V16')
    nodes=np.unique(ids)
    if len(nodes)>2_000_000:raise MemoryError('Five-minute graph exceeds audited 2-million-node memory guard; no truncation')
    lookup=lambda values:np.searchsorted(nodes,np.frombuffer(b''.join(values),dtype='V16'))
    subjects=lookup(actors);raw=np.zeros((len(nodes),2*action_count+1),dtype=np.uint32);edges=[]
    for objects in (one,two):
        present=np.asarray([v is not None for v in objects]);destinations=lookup([v for v in objects if v is not None])
        src=subjects[present];a=actions[present]
        np.add.at(raw,(src,a),1);np.add.at(raw,(destinations,a+action_count),1)
        edges.append(np.stack((src,destinations),axis=1))
    absent=np.asarray([a is None and b is None for a,b in zip(one,two)])
    np.add.at(raw,(subjects[absent],2*action_count),1)
    directed=np.concatenate(edges,axis=0)
    directed=directed[directed[:,0]!=directed[:,1]]
    adjacent=np.unique(np.concatenate((directed,directed[:,::-1]),axis=0),axis=0)
    degree=np.bincount(adjacent[:,0],minlength=len(nodes));indptr=np.concatenate(([0],np.cumsum(degree)))
    return nodes,raw,indptr.astype(np.int64),adjacent[:,1].astype(np.int32)


def independently_check(table,nodes,raw,indptr,indices,action_count):
    with duckdb.connect() as con:
        con.register('ev',table)
        query=f'''SELECT uid,col,count(*) n FROM (
            SELECT actor uid,action col FROM ev WHERE obj1 IS NOT NULL UNION ALL
            SELECT actor uid,action col FROM ev WHERE obj2 IS NOT NULL UNION ALL
            SELECT obj1 uid,action+{action_count} col FROM ev WHERE obj1 IS NOT NULL UNION ALL
            SELECT obj2 uid,action+{action_count} col FROM ev WHERE obj2 IS NOT NULL UNION ALL
            SELECT actor uid,{2*action_count} col FROM ev WHERE obj1 IS NULL AND obj2 IS NULL
            ) GROUP BY uid,col'''
        values=con.execute(query).fetchall()
    check=np.zeros_like(raw)
    if values:
        positions=np.searchsorted(nodes,np.frombuffer(b''.join(v[0] for v in values),dtype='V16'))
        check[positions,np.asarray([v[1] for v in values])]=np.asarray([v[2] for v in values],dtype=np.uint32)
    if not np.array_equal(check,raw) or len(indptr)!=len(nodes)+1 or indptr[-1]!=len(indices):
        raise ValueError('Independent SQL feature aggregation or CSR integrity failed')
    if len(indices) and (indices.min()<0 or indices.max()>=len(nodes)):raise ValueError('Invalid adjacency endpoint')


def compile_graphs(work,actions):
    done=work/'graphs.json'
    if done.exists():return json.loads(done.read_text(encoding='utf-8'))
    (work/'graphs').mkdir(exist_ok=True);(work/'identities').mkdir(exist_ok=True)
    entries=[];sum_values=np.zeros(2*(len(actions)+1)+1);sum_squares=np.zeros_like(sum_values);training_nodes=0;purged=0
    folders=sorted((work/'buckets').glob('host_key=*/window=*'))
    if not folders:raise ValueError('No complete temporal buckets')
    for index,folder in enumerate(folders):
        disk_guard(work);window=int(folder.name.split('=')[1]);host=folder.parent.name.split('=')[1];partition=role(window)
        table=pa.concat_tables([pq.ParquetFile(path).read() for path in sorted(folder.glob('*.parquet'))])
        if partition=='purge':purged+=len(table);continue
        name=f'{host}_{window}';target=work/'graphs'/(name+'.npz');receipt=target.with_suffix('.json')
        if receipt.exists():
            entry=json.loads(receipt.read_text(encoding='utf-8'))
            if file_hash(target)!=entry['sha256']:raise ValueError('Changed graph artifact')
            arrays=np.load(target);raw=arrays['raw']
        else:
            nodes,raw,indptr,indices=graph_arrays(table,len(actions)+1)
            independently_check(table,nodes,raw,indptr,indices,len(actions)+1)
            np.savez_compressed(target,nodes=nodes,raw=raw,indptr=indptr,indices=indices)
            pq.write_table(pa.table(dict(host=[host]*len(nodes),uid=[bytes(v) for v in nodes],role=[partition]*len(nodes))),work/'identities'/(name+'.parquet'),compression='zstd')
            entry=dict(file='graphs/'+target.name,sha256=file_hash(target),host=host,window_start_nanos=window,
                role=partition,nodes=len(nodes),adjacency_edges=len(indices),native_events=len(table),
                independent_sql_vector_check=True)
            save(receipt,entry)
        if partition=='train':
            transformed=np.log1p(raw.astype(np.float64));batch_mean=transformed.mean(0)
            batch_m2=((transformed-batch_mean)**2).sum(0)
            total=training_nodes+len(raw);delta=batch_mean-sum_values
            sum_squares+=batch_m2+delta**2*training_nodes*len(raw)/total
            sum_values+=delta*len(raw)/total;training_nodes=total
        entries.append(entry)
        save(work/'progress.json',dict(phase='compiling_verified_graphs',complete_graphs=len(entries),total_buckets=len(folders)))
        if index%20==0:print(json.dumps(dict(phase='graphs',complete=len(entries),total=len(folders))),flush=True)
    if training_nodes<1 or any(not any(e['role']==r for e in entries) for r in ('train','development','test')):
        raise ValueError('Empty chronological partition')
    means=sum_values;variance=np.maximum(0.,sum_squares/training_nodes)
    std=np.where(variance>1e-24,np.sqrt(variance),1.)
    save(work/'scaler.json',dict(transform='log1p_training_population_zscore',fitted_on='train_only',
        node_windows=training_nodes,means=means.tolist(),stds=std.tolist()))
    with connect(work) as con:
        overlap=con.execute('''WITH memberships AS (SELECT host,uid,bit_or(CASE role WHEN 'train' THEN 1
            WHEN 'development' THEN 2 ELSE 4 END) bits FROM read_parquet(?) GROUP BY host,uid)
            SELECT count(*) FILTER(WHERE bits&3=3),count(*) FILTER(WHERE bits&5=5),
            count(*) FILTER(WHERE bits&6=6) FROM memberships''',[str(work/'identities'/'*.parquet')]).fetchone()
    result=dict(status='full_local_graph_preparation_verified',graphs=entries,feature_count=len(means),
        action_vocabulary=actions+['UNKNOWN'],
        feature_names=['out_ref_'+a for a in actions+['UNKNOWN']]+['in_ref_'+a for a in actions+['UNKNOWN']]+['subject_no_predicate_event_count'],
        purge_gap_events=purged,scaler_sha256=file_hash(work/'scaler.json'),
        native_entity_overlap=dict(zip(('train/development','train/test','development/test'),overlap)),
        security_labels='unknown',scope='All local archives; temporal node-feature imputation with recurring identities')
    save(done,result);return result
