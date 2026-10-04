"""Explicit human evidence can supplement capture output; it is never inferred evidence."""
import json
from .geometry import measurement


def apply_evidence(result, path):
    evidence = json.loads(path.read_text())
    byid = {r['id']:r for r in result['rooms']}
    for item in evidence.get('damage',[]):
        room = byid[item['room_id']]
        surface = item['surface_id']
        if surface not in {w['id'] for w in room['walls']} | {room['id']+'-floor',room['id']+'-ceiling'}:
            raise ValueError('Unknown damage surface')
        if item['class'] not in {'water_stain','crack','mold_suspected','material_loss'}:
            raise ValueError('Unsupported damage class')
        region = {'id':item['id'],'surface_id':surface,'class':item['class'],
                  'polygon_uv':item['polygon_uv'], 'source':'human_annotation',
                  'area':measurement(item.get('area_m2'), item.get('uncertainty_m2',.1),
                                     'm2','human_annotation','reviewed') if item.get('area_m2') is not None else measurement(unit='m2'),
                  'status':'requires_inspection'}
        room['damage_regions'].append(region)
        rule = {'water_stain':'water_stain_requires_moisture_check',
                'mold_suspected':'suspected_mold_requires_specialist_review'}.get(item['class'])
        if rule:
            room['concealed_damage_flags'].append({'region_id':item['id'],'rule_id':rule,
                                                   'action':'inspect', 'diagnosis_confirmed':False})
        room['scope_items'].append({'id':item['id']+'-scope','surface_id':surface,
                                    'action':'inspect_and_document','quantity':region['area'],
                                    'trigger_region_id':item['id'],'cost':None})
    for edge in evidence.get('adjacency',[]):
        if edge['room_a'] not in byid or edge['room_b'] not in byid:
            raise ValueError('Unknown adjacency room ID')
        result['adjacency'].append({**edge,'status':'human_supplied','evidence':'human_annotation','opening_id':edge.get('opening_id')})
    result['warnings'].append('Supplementary human evidence used; automatic damage detection is not implemented.')
