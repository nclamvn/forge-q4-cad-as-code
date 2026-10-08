"""Independent benchmark rules. Geometry is measured, never trusted from proposal notes."""
import copy
from build123d import Box, Circle, Pos, SlotOverall, extrude

CATALOG = [
    dict(id='cable', title='Dời sensor · mở đường cáp', mode='edit',
         description='Dời giao diện sensor và tạo khoảng rỗng xuyên tấm đúng vị trí/kích thước đề bài.'),
    dict(id='lightweight', title='Giảm khối lượng · giữ vùng đỡ', mode='create',
         description='Tạo chi tiết mới, giữ các lỗ lắp và hai vùng đỡ hình học, mở cửa sổ giảm khối lượng.'),
    dict(id='family', title='Thiết kế một họ kích thước', mode='edit',
         description='Sửa mẫu rồi kiểm các chiều rộng khác nhau; hình thực phải thay đổi và vẫn giữ giao diện lắp.')]


def task_rules(case, seed, b):
    # Public, deterministic exercise generation; not a secret/held-out benchmark.
    import random
    rng = random.Random(seed)
    shift = [-rng.choice([8, 10, 12, 14]), rng.choice([-2, 0, 2])]
    rules = [dict(id='sensor_target', kind='sensor_target', xy_mm=shift)]
    if case in ('cable', 'family'):
        rules.append(dict(id='cable_void', kind='clear_slot', xy_mm=[shift[0], 24],
                          length_mm=rng.choice([20, 24, 28]), width_mm=rng.choice([6, 8])))
    else:
        rules[0]['xy_mm'] = [0, 0]
        rules += [dict(id='window_void', kind='clear_circle', xy_mm=[0, 0], diameter_mm=rng.choice([18, 20])),
                  dict(id='side_supports', kind='side_supports'),
                  dict(id='mass_budget', kind='mass_max', max_kg=.070)]
    if case == 'family':
        rules.append(dict(id='width_family', kind='family', parameter='width', values_mm=[88, 94, 98]))
    return rules


def common_volume(shape, tool):
    common = shape & tool
    return common.volume if common is not None else 0.


def task_gates(shape, p, task):
    gates = []
    t = task['brief']['requirements']['plate_thickness_mm']
    for r in task['rules']:
        kind = r['kind']
        if kind == 'family':
            continue
        passed = False
        actual = None
        if kind == 'sensor_target':
            actual = [p['parameters'].get('sensor_shift_x', 0), p['parameters'].get('sensor_shift_y', 0)]
            passed = all(abs(x-y) <= .001 for x, y in zip(actual, r['xy_mm']))
        elif kind in ('clear_slot', 'clear_circle'):
            profile = (SlotOverall(r['length_mm'], r['width_mm']) if kind == 'clear_slot'
                       else Circle(r['diameter_mm']/2))
            # A complete required corridor must be void; a tiny decorative opening cannot pass.
            tool = Pos(*r['xy_mm'], -.01) * extrude(profile, amount=t+.02)
            actual = dict(overlap_mm3=common_volume(shape, tool), probe_volume_mm3=tool.volume)
            passed = actual['overlap_mm3'] <= .001
        elif kind == 'mass_max':
            actual = shape.volume*task['brief']['density_kg_m3']/1e9
            passed = actual <= r['max_kg']
        elif kind == 'side_supports':
            box = shape.bounding_box()
            actual = []
            for sign in (-1, 1):
                x = (box.min.X+3.5) if sign < 0 else (box.max.X-3.5)
                tool = Pos(x, 0, 9.7)*Box(1, 20, 11)
                actual.append(common_volume(shape, tool)/tool.volume)
            passed = min(actual) >= .98
        gates.append(dict(id=r['id'], passed=bool(passed), actual=actual, requirement=r))
    return gates


def family_gates(p, task, reference_path, compiler):
    results = []
    for rule in task['rules']:
        if rule['kind'] != 'family':
            continue
        for value in rule['values_mm']:
            entry = dict(parameter=rule['parameter'], value_mm=value, passed=False)
            try:
                variant = copy.deepcopy(p)
                if rule['parameter'] not in variant['parameters']:
                    raise ValueError('Required family parameter is missing')
                variant['parameters'][rule['parameter']] = value
                variant = compiler.validate(variant, task['brief'])
                shape, _ = compiler.evaluate_graph(variant, False)
                gates, _, _ = compiler.checks(shape, variant, task['brief'], reference_path)
                gates += task_gates(shape, variant, task)
                extent = shape.bounding_box().size.X
                gates.append(dict(id='actual_width', passed=abs(extent-value) < .01, actual=extent))
                entry.update(passed=all(g['passed'] for g in gates), actual_width_mm=extent,
                             gates=gates, volume_mm3=shape.volume)
            except Exception as e:
                entry['error'] = str(e)
            results.append(entry)
    return results


def fixture_program(task, compiler):
    """Software self-check only. Never attributed to an LLM or timed human engineer."""
    p = compiler.example(task['brief'])
    shift = next(r for r in task['rules'] if r['kind'] == 'sensor_target')['xy_mm']
    p['parameters'].update(sensor_shift_x=shift[0], sensor_shift_y=shift[1])
    cut = next(r for r in task['rules'] if r['kind'] in ('clear_slot', 'clear_circle'))
    profile = (dict(kind='slot', length=cut['length_mm'], width=cut['width_mm'])
               if cut['kind'] == 'clear_slot' else dict(kind='circle', diameter=cut['diameter_mm']))
    p['features'] += [dict(id='request_profile', op='sketch', plane='XY', origin=[*cut['xy_mm'], -1], profile=profile),
                      dict(id='request_tool', op='extrude', sketch='request_profile', amount='thickness+2'),
                      dict(id='request_cut', op='boolean', base=p['result'], tool='request_tool', mode='cut')]
    p['result'] = 'request_cut'
    p['name'] = 'Software regression fixture / '+task['case']['id']
    return p
