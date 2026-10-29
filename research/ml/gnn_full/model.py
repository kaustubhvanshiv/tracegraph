"""Matched-width PyG encoders and bounded two-hop CPU sampling."""
import numpy as np
import torch
from torch import nn
from torch_geometric.nn import GCNConv,SAGEConv,GATConv


class GraphReconstructor(nn.Module):
    def __init__(self,family,width):
        super().__init__()
        if family=='gcn':self.first,self.second=GCNConv(width,64),GCNConv(64,32)
        elif family=='graphsage':self.first,self.second=SAGEConv(width,64),SAGEConv(64,32)
        elif family=='gat':self.first,self.second=GATConv(width,16,heads=4),GATConv(64,32,heads=1)
        else:raise ValueError('Unknown approved GNN family')
        self.decoder=nn.Linear(32,width)

    def forward(self,x,edges):
        return self.decoder(self.second(torch.relu(self.first(x,edges)),edges))


def sample(indptr,indices,seeds,rng,fanouts=(10,5)):
    nodes=list(map(int,seeds)); positions={n:i for i,n in enumerate(nodes)};edges=set();frontier=nodes[:]
    if len(positions)!=len(nodes):raise ValueError('Seed nodes must be unique')
    for fanout in fanouts:
        following=set()
        for target in frontier:
            neighbors=indices[indptr[target]:indptr[target+1]]
            if len(neighbors)>fanout:neighbors=rng.choice(neighbors,size=fanout,replace=False)
            for source in neighbors:
                source=int(source)
                if source not in positions:positions[source]=len(nodes);nodes.append(source)
                edges.add((positions[source],positions[target]));following.add(source)
        frontier=sorted(following)
    edge=np.asarray(sorted(edges),dtype=np.int64).T if edges else np.empty((2,0),dtype=np.int64)
    return np.asarray(nodes,dtype=np.int64),edge


def features(raw,nodes,scaler):
    result=(np.log1p(raw[nodes].astype(np.float64))-np.asarray(scaler['means']))/np.asarray(scaler['stds'])
    if not np.isfinite(result).all():raise ValueError('Nonfinite graph input')
    return torch.as_tensor(result,dtype=torch.float32)
