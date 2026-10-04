"""Gate evaluation never substitutes capture estimates for independent truth."""
import math


def gate(status,**values):
    return {'status':status,**values}


def measurements(result):
    out={}
    for r in result['rooms']:
        for kind in ('ceiling_height','floor_area'):
            out[f"{r['id']}/{kind}"]=r[kind]
        for w in r['walls']:
            out[f"{r['id']}/wall/{w['id']}"]=w['length']
        for o in r['openings']:
            out[f"{r['id']}/opening/{o['id']}"]=o['width']
    out['property/footprint_area']=result['footprint_area']
    return out


def evaluate(result,truth,repeat=None,competitor=None):
    if truth.get('independent_measurements') is not True:
        return {'status':'not_evaluated','gates':{'ground_truth':gate('not_evaluated',reason='Independent laser/tape ground truth required')},'dimensions':[]}
    expected=truth.get('measurements',{})
    if not expected:
        return {'status':'not_evaluated','gates':{'ground_truth':gate('not_evaluated',reason='Ground truth has no measurements')},'dimensions':[]}
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in expected.values()):
        raise ValueError('Ground truth values must be positive finite numbers')
    pred=measurements(result)
    rows=[]
    for key,value in expected.items():
        m=pred.get(key)
        known=m is not None and m['value'] is not None
        err=abs(m['value']-value) if known else None
        rows.append({'key':key,'truth':value,'estimate':m['value'] if known else None,
                     'absolute_error':err,'relative_error':err/value if known and value else None,
                     'interval_covers':(m['lower']<=value<=m['upper']) if known else False,
                     'interval_kind':m['interval_kind'] if m else 'unavailable'})
    gates={}
    walls=[r for r in rows if '/wall/' in r['key']]
    tolerance={'photos':.08,'video':.03,'lidar':None}[result['tier']]
    if tolerance is None:
        gates['wall_accuracy']=gate('not_evaluated',reason='LiDAR wall accuracy gate belongs to missing Round 1 contract')
    elif walls:
        failed=[r['key'] for r in walls if r['relative_error'] is None or r['relative_error']>tolerance]
        gates['wall_accuracy']=gate('fail' if failed else 'pass',relative_tolerance=tolerance,failed=failed)
    else:
        gates['wall_accuracy']=gate('not_evaluated',reason='No wall ground truth')
    openings=[r for r in rows if '/opening/' in r['key']]
    predicted_openings={k for k in pred if '/opening/' in k}
    true_openings={r['key'] for r in openings}
    phantom=predicted_openings-true_openings
    correct=sum(r['absolute_error'] is not None and r['absolute_error']<=.02 for r in openings)
    denom=len(true_openings)+len(phantom)
    gates['opening_width']=gate('pass' if denom and correct/denom>=.85 else ('fail' if denom else 'not_evaluated'),
                                correct=correct,scored_openings=denom,phantoms=sorted(phantom),required_fraction=.85)
    heights=[r for r in rows if r['key'].endswith('/ceiling_height')]
    failheight=[r['key'] for r in heights if r['absolute_error'] is None or r['absolute_error']>.015]
    gates['ceiling_height']=gate(('fail' if failheight else 'pass') if heights else 'not_evaluated',failed=failheight,tolerance_m=.015)
    rp=measurements(repeat) if repeat else {}
    if repeat and repeat['tier']!=result['tier']:
        raise ValueError('Repeatability requires the same tier')
    repeatrows=[]
    for row in walls+heights:
        a,b=pred.get(row['key']),rp.get(row['key'])
        delta=abs(a['value']-b['value']) if a and b and a['value'] is not None and b['value'] is not None else None
        allowed=.01 if row in heights else max(.01,row['truth']*.005)
        repeatrows.append({'key':row['key'],'spread_m':delta,'tolerance_m':allowed,'pass':delta is not None and delta<=allowed})
    gates['repeatability']=gate(('pass' if all(r['pass'] for r in repeatrows) else 'fail') if repeat and repeatrows else 'not_evaluated',dimensions=repeatrows)
    footprint=next((r for r in rows if r['key']=='property/footprint_area'),None)
    edges={(e['room_a'],e['room_b']) for e in result['adjacency'] if e['status'] in {'verified','human_supplied'}}
    expected_edges={tuple(e) for e in truth.get('adjacency',[])}
    topology_known='adjacency' in truth and truth.get('no_overlaps_verified') is True
    adjacency_ok={frozenset(e) for e in edges}=={frozenset(e) for e in expected_edges}
    gates['photo_property_stitch']=gate('not_evaluated',reason='Requires photo output, footprint truth and independently verified topology')
    if result['tier']=='photos' and footprint and topology_known:
        good=footprint['relative_error'] is not None and footprint['relative_error']<=.08 and adjacency_ok
        gates['photo_property_stitch']=gate('pass' if good else 'fail',footprint_relative_error=footprint['relative_error'],adjacency_correct=adjacency_ok)
    # Coverage can be reported, but error budgets have no nominal statistical coverage.
    gates['interval_calibration']=gate('not_evaluated',reason='Output error budgets are uncalibrated; held-out confidence interval calibration not implemented',
                                        empirical_coverage=sum(r['interval_covers'] for r in rows)/len(rows),sample_count=len(rows))
    shared=[]
    comp=competitor.get('measurements',{}) if competitor else {}
    for r in rows:
        if r['key'] in comp and r['estimate'] is not None:
            err=abs(comp[r['key']]-r['truth'])
            shared.append({'key':r['key'],'our_error':r['absolute_error'],'app_error':err,'beat_or_tie':r['absolute_error']<=err})
    fraction=sum(r['beat_or_tie'] for r in shared)/len(shared) if shared else None
    gates['head_to_head']=gate(('pass' if fraction>=.70 else 'fail') if shared else 'not_evaluated',fraction=fraction,dimensions=shared,
                               app=competitor.get('app') if competitor else None,version=competitor.get('version') if competitor else None)
    drift=[d.get('drift',{}) for d in result['diagnostics']]
    gates['drift_accountability']=gate('not_evaluated',reason='Requires multi-room on/off ablation against truth',methods=[d.get('method') for d in drift])
    gates['benchmark_composition']=gate('not_evaluated',reason='This evaluator scores one capture; the mandatory multi-capture benchmark must be collected')
    status='fail' if any(g['status']=='fail' for g in gates.values()) else 'incomplete'
    return {'status':status,'gates':gates,'dimensions':rows,'timing_seconds':result['timing_seconds'],
            'bias_diagnosis':'repeatable_but_biased' if heights and failheight and repeat and all(r['pass'] for r in repeatrows if r['key'].endswith('/ceiling_height')) else 'requires_repeated_ground_truth'}
