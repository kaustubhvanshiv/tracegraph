"""Strict, portable NPZ/CSR input contract for native five-minute graphs."""
from pathlib import Path,PurePosixPath
import re
import shutil
import zipfile
import numpy as np
from research.ml.gnn_scoring.artifacts import KIND,WIDTH,read,write,require,fresh_output,load_bundle
from research.ml.node_benchmark.audit_protocol import file_hash

WINDOW=300_000_000_000
MAX_NODES=2_000_000
MAX_EDGES=20_000_000
MAX_GRAPH_BYTES=512*1024**2
MAX_UNCOMPRESSED_BYTES=1200*1024**2
MAX_TOTAL_ROWS=50_000_000
UUID=re.compile(r'^[0-9a-f]{32}$')
GRAPH_KEYS={'file','graph_id','sampling_key','host_uuid','window_start_nanos','nodes','adjacency_edges','native_events','role','sha256'}


def input_manifest(path,schema_sha):
    require(path.stat().st_size<=10*1024**2,'Input manifest exceeds 10 MiB')
    manifest=read(path)
    require(set(manifest)=={'version','kind','feature_schema_sha256','window_nanos','selection','graphs'} and
            manifest['version']==1 and manifest['kind']==KIND and manifest['window_nanos']==WINDOW and
            manifest['feature_schema_sha256']==schema_sha,'Input feature or window contract differs')
    require(isinstance(manifest['graphs'],list) and 0<len(manifest['graphs'])<=10000,'Require 1 to 10000 complete graphs')
    selection=manifest['selection']
    require(isinstance(selection,dict) and set(selection)=={'scope','partition','source_graph_manifest_sha256','all_partition_graphs_included'},
            'Invalid selection provenance fields')
    require(selection['scope'] in ('replay_existing_prepared_graphs','external_prepared_graphs') and
            selection['partition'] in ('train','development','test','external') and
            type(selection['all_partition_graphs_included']) is bool,'Invalid declared input selection')
    if selection['scope']=='external_prepared_graphs':
        require(selection['partition']=='external' and selection['source_graph_manifest_sha256'] is None and
                selection['all_partition_graphs_included'] is False,'External inputs cannot claim recorded partition coverage')
    else:
        require(selection['partition']!='external' and isinstance(selection['source_graph_manifest_sha256'],str) and
                re.fullmatch('[0-9a-f]{64}',selection['source_graph_manifest_sha256']),'Invalid replay manifest binding')
    identities=set();files=set();rows=0;root=path.parent.resolve()
    for entry in manifest['graphs']:
        require(set(entry)==GRAPH_KEYS,'Unexpected graph metadata; security labels are not scorer inputs')
        host=entry['host_uuid'];window=entry['window_start_nanos']
        require(isinstance(host,str) and UUID.fullmatch(host) and host!='0'*32 and
                type(window) is int and window>0 and window%WINDOW==0,'Invalid native host or five-minute boundary')
        identity=f'{host}_{window}'
        require(entry['graph_id']==identity and entry['sampling_key']==f'graphs/{identity}.npz' and identity not in identities,
                'Invalid or duplicate canonical graph identity')
        identities.add(identity)
        relative=entry['file'];require(isinstance(relative,str),'Graph file must be a relative path')
        posix=PurePosixPath(relative)
        require('\\' not in relative and not posix.is_absolute() and
                '..' not in posix.parts and ':' not in relative and posix.suffix=='.npz','Graph file must be a safe relative NPZ path')
        resolved=(root/relative).resolve()
        require(resolved.is_relative_to(root) and resolved not in files,'Input graph path escapes the manifest directory or repeats')
        files.add(resolved)
        require(type(entry['nodes']) is int and 1<=entry['nodes']<=MAX_NODES and
                type(entry['adjacency_edges']) is int and 0<=entry['adjacency_edges']<=MAX_EDGES and
                type(entry['native_events']) is int and entry['native_events']>0,'Invalid graph size or explicit resource cap exceeded')
        require(entry['role'] in ('train','development','test','external') and
                isinstance(entry['sha256'],str) and re.fullmatch('[0-9a-f]{64}',entry['sha256']), 'Invalid graph provenance metadata')
        require(entry['role']==selection['partition'],'Graph role differs from declared selection')
        rows+=entry['nodes']
    require(rows<=MAX_TOTAL_ROWS,'Input exceeds the explicit 50-million-row scoring limit')
    return manifest


def load_graph(path,entry):
    n=entry['nodes'];e=entry['adjacency_edges']
    require(path.stat().st_size<=MAX_GRAPH_BYTES,'Compressed graph exceeds 512 MiB')
    require(file_hash(path)==entry['sha256'],'Input graph fingerprint changed')
    with zipfile.ZipFile(path) as archive:
        require(len(archive.infolist())==4 and {i.filename for i in archive.infolist()}=={'nodes.npy','raw.npy','indptr.npy','indices.npy'},
                'NPZ must contain only nodes raw indptr and indices')
        require(sum(i.file_size for i in archive.infolist())<=MAX_UNCOMPRESSED_BYTES,'Uncompressed graph exceeds memory guard')
        # Inspect shapes before np.load can allocate arrays from untrusted NPY headers.
        expected={'nodes.npy':((n,),(np.dtype('V16'),)), 'raw.npy':((n,WIDTH),(np.dtype('uint32'),)),
            'indptr.npy':((n+1,),(np.dtype('int64'),)), 'indices.npy':((e,),(np.dtype('int32'),np.dtype('int64')))}
        for member in archive.infolist():
            with archive.open(member) as stream:
                version=np.lib.format.read_magic(stream)
                require(version in ((1,0),(2,0)),'Unsupported NPY header version')
                header=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
                shape,fortran,dtype=header(stream,max_header_size=4096)
                wanted_shape,wanted_types=expected[member.filename]
                require(shape==wanted_shape and not fortran and dtype in wanted_types,'NPY header shape/order/dtype differs')
                require(member.file_size==stream.tell()+int(np.prod(shape))*dtype.itemsize,'NPY payload size differs from header')
    with np.load(path,allow_pickle=False) as archive:
        nodes,raw,indptr,indices=(archive[k] for k in ('nodes','raw','indptr','indices'))
    require(nodes.shape==(n,) and nodes.dtype==np.dtype('V16') and np.array_equal(nodes,np.unique(nodes)) and
            not np.any(nodes==np.void(bytes(16))),'Native node UUIDs must be sorted unique nonzero 16-byte values')
    require(raw.shape==(n,WIDTH) and raw.dtype==np.uint32,'Require 115 ordered uint32 raw count columns, without normalization')
    require(indptr.shape==(n+1,) and indptr.dtype==np.int64 and
            indices.shape==(e,) and indices.dtype in (np.dtype('int32'),np.dtype('int64')),'Invalid integer CSR arrays')
    require(indptr[0]==0 and indptr[-1]==e and np.all((indptr>=0)&(indptr<=e)) and
            np.all(np.diff(indptr)>=0),'Invalid CSR offsets')
    if e:
        require(indices.min()>=0 and indices.max()<n,'Invalid CSR neighbor index')
        sources=np.repeat(np.arange(n,dtype=np.int64),np.diff(indptr))
        keys=sources.copy();keys*=n;keys+=indices
        require(np.all(np.diff(keys)>0) and not np.any(sources==indices),'Adjacency must have sorted unique neighbors and no native self edges')
        for start in range(0,e,262144):
            reverse=indices[start:start+262144].astype(np.int64)*n+sources[start:start+262144]
            positions=np.searchsorted(keys,reverse)
            require(np.all(positions<e) and np.array_equal(keys[positions],reverse),'Adjacency must be symmetric')
    outgoing=int(raw[:,:57].sum(dtype=np.uint64));incoming=int(raw[:,57:114].sum(dtype=np.uint64))
    absent=int(raw[:,-1].sum(dtype=np.uint64));events=entry['native_events']
    require(outgoing==incoming and 0<=absent<=events and events-absent<=outgoing<=2*(events-absent),
            'Native Event/reference count totals are inconsistent')
    require(np.all(raw.sum(axis=1,dtype=np.uint64)>0),'Empty native activity node is incompatible')
    return nodes,raw,indptr,indices


def export_inputs(work,bundle_path,bundle_sha,partition,output,graph_keys=None):
    output=fresh_output(output,work,bundle_path)
    bundle,_,schema,_=load_bundle(bundle_path,'cpu',bundle_sha)
    metadata=read(work/'graphs.json')
    require(file_hash(work/'graphs.json')==schema['source_graph_manifest_sha256'],'Replay source manifest differs from the bundle')
    require(partition in ('train','development','test'),'Choose a recorded partition for replay input export')
    candidates=[g for g in metadata['graphs'] if g['role']==partition]
    if graph_keys:
        require(len(set(graph_keys))==len(graph_keys) and set(graph_keys)<={g['file'] for g in candidates},'Unknown or duplicate replay graph key')
        candidates=[g for g in candidates if g['file'] in graph_keys]
    require(candidates,'No graphs selected')
    required=sum((work/g['file']).stat().st_size for g in candidates)
    output.parent.mkdir(parents=True,exist_ok=True)
    require(shutil.disk_usage(output.parent).free>required+128*1024**2,'Insufficient disk for input export')
    output.mkdir();(output/'graphs').mkdir();entries=[]
    for g in candidates:
        host=g['host'];window=g['window_start_nanos'];identity=f'{host}_{window}'
        require(g['file']==f'graphs/{identity}.npz','Unexpected native graph naming/sampling contract')
        source=(work/g['file']).resolve();require(source.is_relative_to(work.resolve()),'Source graph path escapes workspace')
        require(file_hash(source)==g['sha256'],'Prepared graph changed before copy')
        destination=output/g['file'];shutil.copyfile(source,destination)
        require(file_hash(destination)==g['sha256']==file_hash(source),'Copied input graph differs')
        entries.append(dict(file=g['file'],graph_id=identity,sampling_key=g['file'],host_uuid=host,
            window_start_nanos=window,nodes=g['nodes'],adjacency_edges=g['adjacency_edges'],
            native_events=g['native_events'],role=partition,sha256=g['sha256']))
    manifest=dict(version=1,kind=KIND,feature_schema_sha256=bundle['files_sha256']['feature_schema.json'],
        window_nanos=WINDOW,selection=dict(scope='replay_existing_prepared_graphs',partition=partition,
            source_graph_manifest_sha256=file_hash(work/'graphs.json'),all_partition_graphs_included=not bool(graph_keys)),graphs=entries)
    write(output/'input.json',manifest)
    input_manifest(output/'input.json',manifest['feature_schema_sha256'])
    return dict(status='prepared_graph_input_exported',graphs=len(entries),rows=sum(g['nodes'] for g in entries),
        all_partition_graphs_included=not bool(graph_keys),input_manifest_sha256=file_hash(output/'input.json'))
