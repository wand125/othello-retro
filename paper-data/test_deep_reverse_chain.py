#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 wand125 and contributors.
"""Small adversarial checks of the independent array verifier; no search."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('deep_chain_check', HERE/'check_deep_reverse_chain.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--pass-example', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    rejected = []
    with tempfile.TemporaryDirectory(prefix='retro-deep-check-') as folder:
        path = Path(folder)/'mutated.json'
        def rejects(name, mutate):
            changed = copy.deepcopy(data)
            mutate(changed)
            path.write_text(json.dumps(changed))
            try:
                module.check(path)
            except ValueError:
                rejected.append(name)
                return
            raise AssertionError(name + ' was accepted')
        rejects('illegal_coordinate', lambda d: d['edges'][0].update(move='a1'))
        rejects('wrong_mover', lambda d: d['edges'][0].update(mover='O'))
        rejects('false_forced_pass', lambda d: d['edges'][0].update(forced_pass_after_move=True))
        rejects('wrong_following_side', lambda d: d['nodes'][0].update(next_player='X'))
        rejects('descendant_board_only_overclaim', lambda d: d['nodes'][1].update(board_unreachable=True))
        rejects('restricted_encoding_mislabeled_general', lambda d: d['proof'].update(nopass=True))
        rejects('unverified_drat_marked_checked', lambda d: d['proof'].update(drat_independently_checked=True))
        rejects('unverified_prefix_marked_reachable', lambda d: d['prefix_from_reachable_target']['nodes'][1].update(board_unreachable=False))
    # A separate existing legal reference exercises positive explicit and implicit passes.
    example = json.loads(args.pass_example.read_text())
    explicit = module.replay_from_initial(example['moves'], example['board'])
    implicit = module.replay_from_initial([m for m in example['moves'] if m != 'pass'], example['board'])
    assert explicit == implicit and explicit['forced_passes'] > 0
    try:
        module.replay_from_initial(['pass'], module.INITIAL)
    except ValueError:
        rejected.append('voluntary_initial_pass')
    else:
        raise AssertionError('voluntary pass accepted')
    for side in ['O', None]:
        assert not module.cheap_conditions({'board':module.INITIAL, 'next_player':side})['four_disc_goal_includes_initial_black_turn']
    assert all(module.cheap_conditions({'board':module.INITIAL, 'next_player':'X'}).values())
    report = {'status':'passed', 'adversarial_rejections':rejected, 'initial_goal_includes_exact_board_and_black_next':True,
              'separate_forced_pass_example':explicit, 'solver_or_search_execution':False}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
