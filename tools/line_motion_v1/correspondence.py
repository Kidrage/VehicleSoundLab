"""Conservative graph correspondence of discrete peak observations, without amplitude rank."""


def edges(previous,current):
    links=[(i,j) for i,a in enumerate(previous) for j,b in enumerate(current)
           if abs(a['frequency_Hz']-b['frequency_Hz'])<=2]
    vertices={('old',i) for i,j in links}|{('new',j) for i,j in links}
    components=[]
    while vertices:
        seed=min(vertices);component={seed};pending=[seed]
        while pending:
            kind,index=pending.pop()
            neighbors={('new',j) for i,j in links if kind=='old' and i==index} if kind=='old' else {
                ('old',i) for i,j in links if j==index}
            fresh=neighbors-component;component.update(fresh);pending.extend(sorted(fresh))
        vertices-=component
        old=sorted(i for kind,i in component if kind=='old');new=sorted(i for kind,i in component if kind=='new')
        components.append(dict(previous=old,current=new,unique=len(old)==len(new)==1))
    return dict(links=[list(x) for x in links],components=components)


def correspond(frames):
    result=[];transitions=[];next_id=0
    for number,frame in enumerate(frames):
        current=sorted(frame,key=lambda node:node['frequency_Hz'])
        assert len({x['frequency_Hz'] for x in current})==len(current)
        inherited={};ambiguous=set()
        if number:
            previous=result[-1];graph=edges(previous,current)
            for component in graph['components']:
                if component['unique']:
                    i,j=component['previous'][0],component['current'][0];inherited[j]=previous[i]['track_id']
                else:ambiguous.update(component['current'])
            transitions.append(graph)
        row=[]
        for j,node in enumerate(current):
            identity=inherited.get(j)
            if identity is None:identity=next_id;next_id+=1
            row.append(dict(**node,track_id=identity,
                predecessor='unique' if j in inherited else ('ambiguous' if j in ambiguous else 'none')))
        result.append(row)
    return dict(frames=result,transitions=transitions,distinct_observation_tracks=next_id,
        scope='Discrete native-peak correspondence only; no physical source, phase or continuous trajectory claim')
