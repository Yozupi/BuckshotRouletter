from dataclasses import dataclass, replace


SUPPORTED_ITEMS = {
    "adrenaline",
    "beer",
    "cigarettes",
    "expired medicine",
    "handcuffs",
    "handsaw",
    "inverter",
    "magnifying glass",
}


@dataclass(frozen=True)
class State:
    live_shells: int
    blank_shells: int
    current_shell: str
    current_shell_inverted_unknown: bool
    player_hp: int
    dealer_hp: int
    player_items: tuple[tuple[str, int], ...]
    dealer_items: tuple[tuple[str, int], ...]
    player_cuffed: bool
    player_about_to_break_free: bool
    dealer_cuffed: bool
    dealer_about_to_break_free: bool
    damage: int
    turn: int


def _items(value):
    if isinstance(value, dict):
        counts = {str(name).lower(): int(count) for name, count in value.items()}
    else:
        counts = {}
        for name in value or []:
            key = str(name).lower()
            counts[key] = counts.get(key, 0) + 1
    return tuple(sorted((name, count) for name, count in counts.items() if count > 0))


def _count(items, name):
    return dict(items).get(name, 0)


def _consume(items, name):
    counts = dict(items)
    counts[name] -= 1
    if counts[name] <= 0:
        del counts[name]
    return tuple(sorted(counts.items()))


def _give(items, name):
    counts = dict(items)
    counts[name] = counts.get(name, 0) + 1
    return tuple(sorted(counts.items()))


def _add_action(actions, action, transitions):
    actions.append((action, transitions))


def _shell_outcomes(state):
    total = state.live_shells + state.blank_shells
    if state.current_shell == "live":
        return [(1.0, "live", state.live_shells - 1, state.blank_shells)]
    if state.current_shell == "blank":
        return [(1.0, "blank", state.live_shells, state.blank_shells - 1)]
    outcomes = []
    if state.current_shell_inverted_unknown:
        if state.live_shells:
            outcomes.append((state.live_shells / total, "blank", state.live_shells - 1, state.blank_shells))
        if state.blank_shells:
            outcomes.append((state.blank_shells / total, "live", state.live_shells, state.blank_shells - 1))
        return outcomes
    if state.live_shells:
        outcomes.append((state.live_shells / total, "live", state.live_shells - 1, state.blank_shells))
    if state.blank_shells:
        outcomes.append((state.blank_shells / total, "blank", state.live_shells, state.blank_shells - 1))
    return outcomes


def _shoot_actions(state):
    actions = []
    shooter = state.turn
    for target in ("self", "opponent"):
        hit_self = target == "self"
        transitions = []
        for probability, shell, live_shells, blank_shells in _shell_outcomes(state):
            actual_target = shooter if hit_self else 1 - shooter
            damage = state.damage if shell == "live" else 0
            player_hp = max(0, state.player_hp - (damage if actual_target == 0 else 0))
            dealer_hp = max(0, state.dealer_hp - (damage if actual_target == 1 else 0))
            same_turn = hit_self and shell == "blank"
            next_state = replace(
                state,
                live_shells=live_shells,
                blank_shells=blank_shells,
                current_shell="",
                current_shell_inverted_unknown=False,
                player_hp=player_hp,
                dealer_hp=dealer_hp,
                damage=1,
                turn=shooter if same_turn else 1 - shooter,
            )
            transitions.append((probability, next_state))
        target_name = ("self" if hit_self else "dealer") if shooter == 0 else ("self" if hit_self else "player")
        _add_action(actions, {"type": "shoot", "target": target_name}, transitions)
    return actions


def _item_action(state, name, max_hp):
    actions = []
    turn = state.turn
    own_items = state.player_items if turn == 0 else state.dealer_items
    own_hp = state.player_hp if turn == 0 else state.dealer_hp
    own_cuffed = state.dealer_cuffed if turn == 0 else state.player_cuffed
    shell_count = state.live_shells + state.blank_shells

    def with_own_item(name, updated, action):
        if turn == 0:
            next_state = replace(updated, player_items=_consume(state.player_items, name))
        else:
            next_state = replace(updated, dealer_items=_consume(state.dealer_items, name))
        _add_action(actions, action, [(1.0, next_state)])

    def with_own_item_transitions(name, updates, action):
        transitions = []
        for probability, updated in updates:
            if turn == 0:
                next_state = replace(updated, player_items=_consume(state.player_items, name))
            else:
                next_state = replace(updated, dealer_items=_consume(state.dealer_items, name))
            transitions.append((probability, next_state))
        _add_action(actions, action, transitions)

    if name == "cigarettes" and _count(own_items, name) and own_hp < max_hp:
        healed = min(max_hp, own_hp + 1)
        updated = replace(state, player_hp=healed) if turn == 0 else replace(state, dealer_hp=healed)
        with_own_item(name, updated, {"type": "use_item", "item": name})

    if name == "handsaw" and _count(own_items, name) and state.damage == 1:
        updated = replace(state, damage=2)
        with_own_item(name, updated, {"type": "use_item", "item": name})

    if name == "handcuffs" and _count(own_items, name) and not own_cuffed and shell_count > 1:
        if turn == 0:
            updated = replace(state, dealer_cuffed=True, dealer_about_to_break_free=False)
        else:
            updated = replace(state, player_cuffed=True, player_about_to_break_free=False)
        with_own_item(name, updated, {"type": "use_item", "item": name})

    if name == "beer" and _count(own_items, name) and shell_count > 1:
        updates = [
            (
                probability,
                replace(
                    state,
                    live_shells=live_shells,
                    blank_shells=blank_shells,
                    current_shell="",
                    current_shell_inverted_unknown=False,
                ),
            )
            for probability, _, live_shells, blank_shells in _shell_outcomes(state)
        ]
        with_own_item_transitions(name, updates, {"type": "use_item", "item": name})

    if name == "inverter" and _count(own_items, name):
        if not state.current_shell:
            updated = replace(
                state,
                current_shell_inverted_unknown=not state.current_shell_inverted_unknown,
            )
        elif state.current_shell == "live":
            updated = replace(
                state,
                live_shells=state.live_shells - 1,
                blank_shells=state.blank_shells + 1,
                current_shell="blank",
                current_shell_inverted_unknown=False,
            )
        else:
            updated = replace(
                state,
                live_shells=state.live_shells + 1,
                blank_shells=state.blank_shells - 1,
                current_shell="live",
                current_shell_inverted_unknown=False,
            )
        with_own_item(name, updated, {"type": "use_item", "item": name})

    if name == "magnifying glass" and _count(own_items, name) and not state.current_shell and shell_count:
        updates = []
        if state.current_shell_inverted_unknown and state.live_shells:
            updates.append((
                state.live_shells / shell_count,
                replace(
                    state,
                    live_shells=state.live_shells - 1,
                    blank_shells=state.blank_shells + 1,
                    current_shell="blank",
                    current_shell_inverted_unknown=False,
                ),
            ))
        elif not state.current_shell_inverted_unknown and state.live_shells:
            updates.append((state.live_shells / shell_count, replace(state, current_shell="live")))
        if state.current_shell_inverted_unknown and state.blank_shells:
            updates.append((
                state.blank_shells / shell_count,
                replace(
                    state,
                    live_shells=state.live_shells + 1,
                    blank_shells=state.blank_shells - 1,
                    current_shell="live",
                    current_shell_inverted_unknown=False,
                ),
            ))
        elif not state.current_shell_inverted_unknown and state.blank_shells:
            updates.append((state.blank_shells / shell_count, replace(state, current_shell="blank")))
        with_own_item_transitions(name, updates, {"type": "use_item", "item": name})

    if name == "expired medicine" and _count(own_items, name):
        healed_hp = min(max_hp, own_hp + 2)
        lost_hp = max(0, own_hp - 1)
        if turn == 0:
            healed = replace(state, player_hp=healed_hp, player_items=_consume(state.player_items, name))
            hurt = replace(state, player_hp=lost_hp, player_items=_consume(state.player_items, name))
        else:
            healed = replace(state, dealer_hp=healed_hp, dealer_items=_consume(state.dealer_items, name))
            hurt = replace(state, dealer_hp=lost_hp, dealer_items=_consume(state.dealer_items, name))
        _add_action(actions, {"type": "use_item", "item": name}, [(0.5, healed), (0.5, hurt)])

    return actions


def _item_actions(state, max_hp):
    actions = []
    turn = state.turn
    own_items = state.player_items if turn == 0 else state.dealer_items
    other_items = state.dealer_items if turn == 0 else state.player_items

    for name, count in own_items:
        if not count:
            continue
        if name != "adrenaline":
            actions.extend(_item_action(state, name, max_hp))
            continue

        for stolen_item, count in other_items:
            if count <= 0 or stolen_item not in SUPPORTED_ITEMS - {"adrenaline"}:
                continue
            stolen_own = _give(_consume(own_items, "adrenaline"), stolen_item)
            stolen_other = _consume(other_items, stolen_item)
            if turn == 0:
                after_steal = replace(state, player_items=stolen_own, dealer_items=stolen_other)
            else:
                after_steal = replace(state, dealer_items=stolen_own, player_items=stolen_other)
            for _, transitions in _item_action(after_steal, stolen_item, max_hp):
                action = {"type": "steal_and_use", "item": "adrenaline", "stolen_item": stolen_item}
                _add_action(actions, action, transitions)

    return actions


def solve(state_data):
    live_shells = int(state_data.get("live_shells_remaining", 0))
    blank_shells = int(state_data.get("blank_shells_remaining", 0))
    if live_shells < 0 or blank_shells < 0:
        raise ValueError("shell counts must be non-negative.")
    if live_shells + blank_shells == 0:
        raise ValueError("The current magazine has no remaining shells.")
    current_shell = str(state_data.get("current_shell", "")).lower()
    if not bool(state_data.get("current_shell_known", False)):
        current_shell = ""
    elif current_shell not in {"live", "blank"}:
        raise ValueError("current_shell must be 'live' or 'blank' when known.")
    elif (current_shell == "live" and live_shells == 0) or (current_shell == "blank" and blank_shells == 0):
        raise ValueError("known current shell is inconsistent with remaining counts.")

    max_hp = max(1, int(state_data.get("max_hp", 1)))
    player_items = _items(state_data.get("player_items", {}))
    dealer_items = _items(state_data.get("dealer_items", {}))
    initial = State(
        live_shells=live_shells,
        blank_shells=blank_shells,
        current_shell=current_shell,
        current_shell_inverted_unknown=bool(state_data.get("current_shell_inverted_unknown", False)) and not current_shell,
        player_hp=max(0, int(state_data.get("player_hp", 0))),
        dealer_hp=max(0, int(state_data.get("dealer_hp", 0))),
        player_items=player_items,
        dealer_items=dealer_items,
        player_cuffed=bool(state_data.get("player_cuffed", False)),
        player_about_to_break_free=bool(state_data.get("player_about_to_break_free", False)),
        dealer_cuffed=bool(state_data.get("dealer_cuffed", False)),
        dealer_about_to_break_free=bool(state_data.get("dealer_about_to_break_free", False)),
        damage=2 if int(state_data.get("current_shotgun_damage", 1)) >= 2 else 1,
        turn=0,
    )

    value_cache = {}
    visited = 0

    def score_state(current):
        if current.player_hp <= 0:
            return 0.0
        if current.dealer_hp <= 0:
            return 1.0
        total_hp = current.player_hp + current.dealer_hp
        return current.player_hp / total_hp if total_hp else 0.5

    def score_after_shot(current):
        if current.player_hp <= 0 or current.dealer_hp <= 0 or not current.live_shells + current.blank_shells:
            return score_state(current)
        scores = []
        for target in ("self", "opponent"):
            hit_self = target == "self"
            expected = 0.0
            for probability, shell, _, _ in _shell_outcomes(current):
                actual_target = current.turn if hit_self else 1 - current.turn
                damage = current.damage if shell == "live" else 0
                player_hp = max(0, current.player_hp - (damage if actual_target == 0 else 0))
                dealer_hp = max(0, current.dealer_hp - (damage if actual_target == 1 else 0))
                if player_hp <= 0:
                    outcome = 0.0
                elif dealer_hp <= 0:
                    outcome = 1.0
                else:
                    total_hp = player_hp + dealer_hp
                    outcome = player_hp / total_hp if total_hp else 0.5
                expected += probability * outcome
            scores.append(expected)
        return max(scores) if current.turn == 0 else min(scores)

    def action_ordering(entry, maximizing):
        action, transitions = entry
        estimate = 0.0
        item = action.get("stolen_item", action.get("item", ""))
        for probability, next_state in transitions:
            outcome = score_after_shot(next_state)
            if item == "handcuffs":
                outcome += 0.03 if maximizing else -0.03
            estimate += probability * outcome
        return -estimate if maximizing else estimate

    def chance_score(transitions, maximizing, alpha, beta):
        score = 0.0
        total_probability = sum(probability for probability, _ in transitions)
        for index, (probability, next_state) in enumerate(transitions):
            remaining = sum(weight for weight, _ in transitions[index + 1:])
            if maximizing:
                if score + probability + remaining <= alpha:
                    return None
                threshold = (alpha - score - remaining) / probability
                if next_state.turn == 1 and 0 <= threshold < 1:
                    upper_bound = value(next_state, threshold, float("inf"))
                    if upper_bound <= threshold:
                        return None
            else:
                if score >= beta:
                    return None
                threshold = (beta - score) / probability
                if next_state.turn == 0 and 0 < threshold <= 1:
                    lower_bound = value(next_state, float("-inf"), threshold)
                    if lower_bound >= threshold:
                        return None
            outcome = value(next_state, exact_required=True)
            score += probability * outcome
        return score / total_probability

    def ordered_actions(current):
        actions = _item_actions(current, max_hp)
        actions.extend(_shoot_actions(current))
        maximizing = current.turn == 0
        actions.sort(key=lambda entry: action_ordering(entry, maximizing))
        return tuple(actions)

    def value(current, alpha=float("-inf"), beta=float("inf"), exact_required=False):
        nonlocal visited
        visited += 1
        if current.player_hp <= 0:
            return 0.0
        if current.dealer_hp <= 0:
            return 1.0
        if current.live_shells + current.blank_shells == 0:
            return current.player_hp / (current.player_hp + current.dealer_hp)
        lower, upper, exact = value_cache.get(
            current,
            (float("-inf"), float("inf"), None),
        )
        if exact is not None:
            return exact
        if exact_required:
            alpha = float("-inf")
            beta = float("inf")
        else:
            alpha = max(alpha, lower)
            beta = min(beta, upper)
            if alpha >= beta:
                if lower >= beta:
                    return lower
                return upper

        if current.turn == 0 and current.player_cuffed:
            if not current.player_about_to_break_free:
                return value(replace(current, turn=1, player_about_to_break_free=True), alpha, beta, exact_required)
            current = replace(current, player_cuffed=False, player_about_to_break_free=False)
        elif current.turn == 1 and current.dealer_cuffed:
            if not current.dealer_about_to_break_free:
                return value(replace(current, turn=0, dealer_about_to_break_free=True), alpha, beta, exact_required)
            current = replace(current, dealer_cuffed=False, dealer_about_to_break_free=False)

        search_alpha = alpha
        search_beta = beta
        maximizing = current.turn == 0
        actions = ordered_actions(current)
        best = float("-inf") if maximizing else float("inf")
        for _, transitions in actions:
            if len(transitions) == 1:
                probability, next_state = transitions[0]
                score = probability * value(next_state, alpha, beta)
            else:
                score = chance_score(transitions, maximizing, alpha, beta)
                if score is None:
                    if maximizing and best == float("-inf"):
                        best = alpha
                    elif not maximizing and best == float("inf"):
                        best = beta
                    continue
            if maximizing:
                best = max(best, score)
                alpha = max(alpha, best)
            else:
                best = min(best, score)
                beta = min(beta, best)
            if alpha >= beta:
                break
        if best <= search_alpha:
            upper = min(upper, best)
        elif best >= search_beta:
            lower = max(lower, best)
        else:
            lower = best
            upper = best
            exact = best
        if lower == upper:
            exact = lower
        value_cache[current] = (lower, upper, exact)
        return best

    if not bool(state_data.get("player_can_act", True)):
        return {
            "status": "waiting",
            "objective": "maximize expected player win share against an optimal dealer under shuffled-shell uncertainty",
            "message": "Waiting for the player's action window.",
            "evaluated_states": visited,
        }

    root_actions = _item_actions(initial, max_hp)
    root_actions.extend(_shoot_actions(initial))
    root_actions.sort(
        key=lambda entry: (
            action_ordering(entry, True),
            0 if entry[0]["type"] == "shoot" else 1,
            entry[0].get("item", entry[0].get("target", "")),
        )
    )
    best_score = None
    best_action = None
    for action, transitions in root_actions:
        if best_score is None:
            score = chance_score(transitions, True, float("-inf"), float("inf"))
        elif len(transitions) == 1:
            probability, next_state = transitions[0]
            score = probability * value(next_state, best_score, float("inf"))
            if score <= best_score:
                continue
            score = probability * value(next_state, exact_required=True)
        else:
            score = chance_score(transitions, True, best_score, float("inf"))
            if score is None:
                continue
        if best_score is None or score > best_score:
            best_score = score
            best_action = action

    unknown_items = {
        name
        for name, count in initial.player_items + initial.dealer_items
        if count > 0 and name not in SUPPORTED_ITEMS
    }
    return {
        "status": "ready",
        "objective": "maximize expected player win share against an optimal dealer under shuffled-shell uncertainty through the current magazine",
        "magazine_end_estimate": "If the magazine empties with both alive, continuation is estimated as player_hp / (player_hp + dealer_hp).",
        "best_action": best_action,
        "player_win_share": round(best_score, 6),
        "candidates": [{"action": best_action, "player_win_share": round(best_score, 6)}],
        "unmodeled_items": sorted(unknown_items),
        "evaluated_states": visited,
    }
