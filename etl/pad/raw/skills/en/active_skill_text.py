import logging
from collections import OrderedDict
from copy import deepcopy
from fractions import Fraction
from typing import List

from pad.raw.skills.active_skill_info import ASConditional, OrbLine, PartWithTextAndCount
from pad.raw.skills.en.skill_common import EnBaseTextConverter, capitalize_first, indef_article, minmax, noun_count, \
    ordinal, pluralize
from pad.raw.skills.skill_common import fmt_mult

human_fix_logger = logging.getLogger('human_fix')

ROW_INDEX = {
    0: 'the top row',
    1: 'the 2nd row from the top',
    2: 'the middle row',
    3: 'the 2nd row from the bottom',
    4: 'the bottom row',
}

COLUMN_INDEX = {
    0: 'the far left column',
    1: 'the 2nd column from the left',
    2: 'the 3rd column from the left',
    3: 'the 3rd column from the right',
    4: 'the 2nd column from the right',
    5: 'the far right column',
}


class EnASTextConverter(EnBaseTextConverter):
    def fmt_repeated(self, text, amount):
        return '{} {:s}'.format(text, noun_count('time', amount))

    def fmt_mass_atk(self, mass_attack):
        return 'all enemies' if mass_attack else 'an enemy'

    def fmt_duration(self, duration, max_duration=None):
        if max_duration and duration != max_duration:
            return 'For {}~{:s}, '.format(duration, noun_count('turn', max_duration))
        else:
            return 'For {:s}, '.format(noun_count('turn', duration))

    def attr_nuke_convert(self, act):
        return 'Deal ' + fmt_mult(act.multiplier) + 'x ATK ' + self.ATTRIBUTES[int(
            act.attribute)] + ' damage to ' + self.fmt_mass_atk(act.mass_attack)

    def fixed_attr_nuke_convert(self, act):
        return 'Deal ' + '{:,}'.format(act.damage) + ' ' + self.ATTRIBUTES[int(
            act.attribute)] + ' damage to ' + self.fmt_mass_atk(act.mass_attack)

    def self_att_nuke_convert(self, act):
        return 'Deal ' + fmt_mult(act.multiplier) + \
               'x ATK damage to ' + self.fmt_mass_atk(act.mass_attack)

    def shield_convert(self, act):
        return self.fmt_duration(act.duration) + self.fmt_reduct_text(act.shield)

    def elemental_shield_convert(self, act):
        skill_text = self.fmt_duration(act.duration)
        if act.shield == 1:
            skill_text += 'void all ' + self.ATTRIBUTES[int(act.attribute)] + ' damage'
        else:
            skill_text += 'reduce ' + \
                          self.ATTRIBUTES[int(act.attribute)] + ' damage by ' + \
                          fmt_mult(act.shield * 100) + '%'
        return skill_text

    def drain_attack_convert(self, act):
        skill_text = 'Deal ' + \
                     fmt_mult(act.atk_multiplier) + 'x ATK damage to ' + self.fmt_mass_atk(act.mass_attack)
        if act.recover_multiplier == 1:
            skill_text += ' and recover the same amount as HP'
        else:
            skill_text += ' and recover ' + \
                          fmt_mult(act.recover_multiplier * 100) + '% of the damage as HP'
        return skill_text

    def poison_convert(self, act):
        return 'Poison all enemies (' + fmt_mult(act.multiplier) + 'x ATK)'

    def ctw_convert(self, act):
        return 'Freely move orbs for {:s}'.format(noun_count('second', act.duration))

    def gravity_convert(self, act):
        return 'Reduce enemies\' remaining HP by ' + fmt_mult(act.percentage_hp * 100) + '%'

    def heal_active_convert(self, act):
        hp = getattr(act, 'hp', 0)
        rcv_mult = getattr(act, 'rcv_multiplier_as_hp', 0)
        php = getattr(act, 'percentage_max_hp', 0)
        trcv_mult = getattr(act, 'team_rcv_multiplier_as_hp', 0)
        unbind = getattr(act, 'card_bind', 0)
        awoken_unbind = getattr(act, 'awoken_bind', 0)

        skill_text = ('Recover ' + '{:,}'.format(hp) + ' HP' if hp != 0 else
                      ('Recover ' + fmt_mult(rcv_mult) + 'x RCV as HP' if rcv_mult != 0 else
                       ('Recover all HP' if php == 1 else
                        ('Recover ' + fmt_mult(php * 100) + '% of max HP' if php > 0 else
                         ('Recover HP equal to ' + fmt_mult(trcv_mult) + 'x team\'s total RCV' if trcv_mult > 0 else
                          '')))))

        if unbind or awoken_unbind:
            if skill_text:
                skill_text += '; '
            skill_text += ('Remove all binds and awoken skill binds' if (unbind >= 9999 and awoken_unbind) else
                           ('Reduce binds and awoken skill binds by {:s}'.format(noun_count('turn', awoken_unbind)) if (
                                   unbind and awoken_unbind) else
                            ('Remove all binds' if unbind >= 9999 else
                             ('Reduce binds by {:s}'.format(noun_count('turn', unbind)) if unbind else
                              ('Remove all awoken skill binds' if awoken_unbind >= 9999 else
                               ('Reduce awoken skill binds by {:s}'.format(noun_count('turn', awoken_unbind))))))))
        return skill_text

    def delay_convert(self, act):
        return 'Delay enemies\' next attack by {:s}'.format(noun_count('turn', act.turns))

    def defense_reduction_convert(self, act):
        return self.fmt_duration(act.duration) + \
               'reduce enemies\' defense by ' + fmt_mult(act.shield * 100) + '%'

    def double_orb_convert(self, act):
        if len(act.to_attr) == 1:
            skill_text = 'Change {} and {} orbs to {} orbs'.format(self.ATTRIBUTES[int(act.from_attr[0])],
                                                                   self.ATTRIBUTES[int(act.from_attr[1])],
                                                                   self.ATTRIBUTES[int(act.to_attr[0])])
        else:
            skill_text = 'Change {} orbs to {} orbs; Change {} orbs to {} orbs'.format(
                self.ATTRIBUTES[int(act.from_attr[0])],
                self.ATTRIBUTES[int(act.to_attr[0])],
                self.ATTRIBUTES[int(act.from_attr[1])],
                self.ATTRIBUTES[int(act.to_attr[1])])

        return skill_text

    def damage_to_att_enemy_convert(self, act):
        return 'Deal ' + '{:,}'.format(act.damage) + ' ' + self.ATTRIBUTES[int(
            act.attack_attribute)] + ' damage to all ' + self.ATTRIBUTES[int(act.enemy_attribute)] + ' Att. enemies'

    def rcv_boost_convert(self, act):
        return self.fmt_duration(act.duration) + fmt_mult(act.multiplier) + 'x RCV'

    def attribute_attack_boost_convert(self, act):
        skill_text = ''
        if act.rcv_boost:
            skill_text += self.fmt_duration(act.duration) + fmt_mult(act.multiplier) + 'x RCV'
        if skill_text:
            skill_text += '; '
        skill_text += self.fmt_duration(act.duration) + self.fmt_stats_type_attr_bonus(act, atk=act.multiplier)
        return skill_text

    def mass_attack_convert(self, act):
        return self.fmt_duration(act.duration) + 'all attacks become mass attack'

    def enhance_convert(self, act):
        for_attr = act.orbs
        skill_text = ''

        if for_attr:
            if not len(for_attr) == 6:
                color_text = self.concat_list_and([self.ATTRIBUTES[i] for i in for_attr])
                skill_text = 'Enhance all ' + color_text + ' orbs'
            else:
                skill_text = 'Enhance all orbs'
        return skill_text

    def lock_convert(self, act):
        for_attr = act.orbs
        amount_text = 'all' if act.count >= 42 else str(act.count)
        color_text = '' if len(for_attr) == 10 else self.attributes_to_str(for_attr)
        result = 'Lock {} {} orbs'.format(amount_text, color_text)
        return ' '.join(result.split())

    def laser_convert(self, act):
        return 'Deal ' + '{:,}'.format(act.damage) + \
               ' fixed damage to ' + self.fmt_mass_atk(act.mass_attack)

    def no_skyfall_convert(self, act):
        return self.fmt_duration(act.duration) + 'no skyfall'

    def enhance_skyfall_convert(self, act):
        return self.fmt_duration(act.duration) + 'enhanced orbs are more likely to appear by ' + \
               fmt_mult(act.percentage_increase * 100) + '%'

    def auto_heal_convert(self, act):
        skill_text = ''
        unbind = act.card_bind
        awoken_unbind = act.awoken_bind
        if act.duration:
            skill_text += self.fmt_duration(act.duration) + 'recover ' + \
                          fmt_mult(act.percentage_max_hp * 100) + '% of max HP'
        if unbind or awoken_unbind:
            if skill_text:
                skill_text += '; '
            skill_text += ('Remove all binds and awoken skill binds' if (unbind >= 9999 and awoken_unbind) else
                           ('Reduce binds and awoken skill binds by {:s}'.format(noun_count('turn', awoken_unbind)) if (
                                   unbind and awoken_unbind) else
                            ('Remove all binds' if unbind >= 9999 else
                             ('Reduce binds by {:s}'.format(noun_count('turn', unbind)) if unbind else
                              ('Remove all awoken skill binds' if awoken_unbind >= 9999 else
                               ('Reduce awoken skill binds by {:s}'.format(noun_count('turn', awoken_unbind))))))))

        return skill_text

    def absorb_mechanic_void_convert(self, act):
        if act.attribute_absorb and act.damage_absorb:
            return self.fmt_duration(act.duration) + \
                   'bypass damage absorb shield and att. absorb shield effects'
        elif act.attribute_absorb and not act.damage_absorb:
            return self.fmt_duration(act.duration) + 'bypass att. absorb shield effects'
        elif not act.attribute_absorb and act.damage_absorb:
            return self.fmt_duration(act.duration) + 'bypass damage absorb shield effects'
        else:
            return None

    def void_mechanic_convert(self, act):
        return self.fmt_duration(act.duration) + 'bypass void damage shield effects'

    def true_gravity_convert(self, act):
        return 'Deal damage equal to ' + \
               fmt_mult(act.percentage_max_hp * 100) + '% of enemies\' max HP'

    def extra_combo_convert(self, act):
        return self.fmt_duration(act.duration) + \
               'increase combo count by ' + str(act.combos)

    def awakening_heal_convert(self, act):
        skill_text = 'Heal {:d}x RCV for each '.format(int(act.amount_per))
        awakens = [f"{{{{ awoskills.id{a}|default('???') }}}}" for a in act.awakenings if a]
        skill_text += self.concat_list_and(awakens)
        skill_text += ' awakening on the team'
        return skill_text

    def awakening_attack_boost_convert(self, act):
        skill_text = self.fmt_duration(act.duration) + 'increase ATK by ' + \
                     fmt_mult(act.amount_per * 100) + '% for each '
        awakens = [f"{{{{ awoskills.id{a}|default('???') }}}}" for a in act.awakenings if a]
        skill_text += self.concat_list_and(awakens)
        skill_text += ' awakening on the team'
        return skill_text

    def awakening_shield_convert(self, act):
        skill_text = self.fmt_duration(act.duration) + 'reduce damage taken by ' + \
                     fmt_mult(act.amount_per * 100) + '% for each '
        awakens = [f"{{{{ awoskills.id{a}|default('???') }}}}" for a in act.awakenings if a]
        skill_text += self.concat_list_and(awakens)
        skill_text += ' awakening on the team'
        return skill_text

    def awakening_stat_boost_convert(self, act):
        skill_text = self.fmt_duration(act.duration)
        if act.atk_per and act.atk_per == act.rcv_per:
            skill_text += f"increase ATK & RCV by {fmt_mult(act.atk_per * 100)}%"
        else:
            if act.atk_per:
                skill_text += f"increase ATK by {fmt_mult(act.atk_per * 100)}%"
                if act.rcv_per:
                    skill_text += " and "
            if act.rcv_per:
                skill_text += f"increase RCV by {fmt_mult(act.rcv_per * 100)}%"
        awakenings = self.concat_list_and(f"{{{{ awoskills.id{a}|default('???') }}}}"
                                          for a in act.awakenings if a)
        skill_text += f" for each {awakenings} awakening on the team"
        return skill_text

    def change_enemies_attribute_convert(self, act):
        if act.turns is not None:
            skill_text = self.fmt_duration(act.turns) + 'change'
        else:
            skill_text = 'Change'
        return skill_text + ' all enemies to ' + self.ATTRIBUTES[act.attribute] + ' Att.'

    def haste_convert(self, act):
        return 'Charge all allies\' skills by {:s}'.format(noun_count('turn', act.turns, act.max_turns))

    def hp_boost(self, act):
        return self.fmt_duration(act.duration) + f'{fmt_mult(act.hp)}x HP'

    def random_orb_change_convert(self, act):
        from_attr = act.from_attr
        to_attr = act.to_attr
        skill_text = 'Change '
        if from_attr == self.ALL_ATTRS:
            skill_text += 'all orbs to '
        else:
            skill_text += self.concat_list_and([self.ATTRIBUTES[i] for i in from_attr]) + ' orbs to '
        skill_text += self.concat_list_and([self.ATTRIBUTES[i] for i in to_attr]) + ' orbs'
        return skill_text

    def attack_attr_x_team_atk_convert(self, act):
        skill_text = 'Deal ' + self.ATTRIBUTES[act.attack_attribute] + \
                     ' damage equal to ' + fmt_mult(act.multiplier) + 'x of team\'s total '
        skill_text += self.concat_list_and([self.ATTRIBUTES[a] for a in act.team_attributes]) + ' ATK to '
        skill_text += self.fmt_mass_atk(act.mass_attack)
        return skill_text

    def spawn_orb_convert(self, act):
        skill_text = 'Create {} '.format(act.amount)
        skill_text += self.concat_list_and([self.ATTRIBUTES[o] for o in act.orbs])
        skill_text += ' ' + pluralize('orb', act.amount)
        if act.orbs != act.excluding_orbs and act.excluding_orbs != []:
            templist = set(act.excluding_orbs) - set(act.orbs)
            skill_text += ' over non '
            skill_text += self.concat_list_and([self.ATTRIBUTES[o] for o in templist]) + ' orbs'
        elif len(act.excluding_orbs) == 0:
            skill_text += ' over any ' + pluralize('orb', act.amount)
        return skill_text

    def double_spawn_orb_convert(self, act):
        skill_text = self.spawn_orb_convert(act)
        skill_text += ', and create {} '.format(act.amount2)
        skill_text += self.concat_list_and([self.ATTRIBUTES[o] for o in act.orbs2])
        skill_text += ' ' + pluralize('orb', act.amount2)
        if act.orbs != act.excluding_orbs2 and act.excluding_orbs2 != []:
            templist = set(act.excluding_orbs2) - set(act.orbs2)
            skill_text += ' over non '
            skill_text += self.concat_list_and([self.ATTRIBUTES[o] for o in templist]) + ' orbs'
        elif len(act.excluding_orbs2) == 0:
            skill_text += ' over any ' + pluralize('orb', act.amount2)
        return skill_text

    def move_time_buff_convert(self, act):
        if act.static == 0:
            return self.fmt_duration(act.duration) + \
                   fmt_mult(act.percentage) + 'x orb move time'
        elif act.percentage == 0:
            return self.fmt_duration(act.duration) + \
                   'increase orb move time by {:s}'.format(noun_count('second', fmt_mult(act.static)))
        raise ValueError()

    def row_change_convert(self, act):
        return self._line_change_convert(act.rows, ROW_INDEX)

    def column_change_convert(self, act):
        return self._line_change_convert(act.columns, COLUMN_INDEX)

    def _line_change_convert(self, lines, index):
        skill_text = []
        # TODO: simplify this
        lines = [(index[line.index],
                  self.attributes_to_str(line.attrs) + ' orbs'
                  if isinstance(line.attrs, list) else line.attrs)
                 for line in lines]
        skip = 0
        for c, line in enumerate(lines):
            if skip:
                skip -= 1
                continue
            elif c == len(lines) - 1 or lines[c + 1][1] != line[1]:
                skill_text.append('change {} to {}'.format(*line))
            else:
                while c + skip < len(lines) and lines[c + skip][1] == line[1]:
                    skip += 1
                formatted = ' and '.join(map(lambda l: l[0], lines[c:c + skip]))
                skill_text.append("change {} to {}".format(formatted, line[1]))
                skip -= 1
        return capitalize_first(' and '.join(skill_text))

    def change_skyfall_convert(self, act):
        skill_text = self.fmt_duration(act.duration, act.max_duration)
        rate = fmt_mult(act.percentage * 100)

        if rate == '100':
            skill_text += 'only {} orbs will appear'.format(self.concat_list_and(self.ATTRIBUTES[i] for i in act.orbs))
        else:
            skill_text += '{} orbs are more likely to appear by {}%'.format(
                self.concat_list_and(self.ATTRIBUTES[i] for i in act.orbs),
                rate)
        return skill_text

    def random_nuke_convert(self, act):
        if act.minimum_multiplier != act.maximum_multiplier:
            return 'Randomized ' + self.ATTRIBUTES[act.attribute] + ' damage to ' + self.fmt_mass_atk(
                act.mass_attack) + '(' + fmt_mult(act.minimum_multiplier) + '~' + fmt_mult(
                act.maximum_multiplier) + 'x)'
        else:
            return 'Deal ' + fmt_mult(act.maximum_multiplier) + 'x ' + \
                   self.ATTRIBUTES[act.attribute] + ' damage to ' + self.fmt_mass_atk(act.mass_attack)

    def counterattack_convert(self, act):
        return self.fmt_duration(act.duration) + fmt_mult(act.multiplier) + \
               'x ' + self.ATTRIBUTES[act.attribute] + ' counterattack'

    def board_change_convert(self, act):
        skill_text = 'Change all orbs to '
        skill_text += self.concat_list_and([self.ATTRIBUTES[a] for a in act.to_attr]) + ' orbs'
        return skill_text

    def suicide_random_nuke_convert(self, act):
        skill_text = self.suicide_convert(act) + '; '
        skill_text += 'Deal ' + minmax(act.maximum_multiplier, act.minimum_multiplier, fmt=True) \
                      + 'x ' + self.ATTRIBUTES[act.attribute] + ' damage to ' + self.fmt_mass_atk(act.mass_attack)
        return skill_text

    def suicide_nuke_convert(self, act):
        skill_text = self.suicide_convert(act) + '; '
        skill_text += 'Deal ' + '{:,}'.format(act.damage) + ' ' + self.ATTRIBUTES[
            act.attribute] + ' damage to ' + self.fmt_mass_atk(
            act.mass_attack)
        return skill_text

    def suicide_convert(self, act):
        if act.hp_remaining == 0:
            return 'Reduce HP to 1'
        else:
            return 'Reduce HP by ' + fmt_mult((1 - act.hp_remaining) * 100) + '%'

    def type_attack_boost_convert(self, act):
        skill_text = self.fmt_duration(act.duration) + fmt_mult(act.multiplier) + 'x ATK for '
        skill_text += self.concat_list_and([self.TYPES[t] for t in act.types]) + ' '
        skill_text += pluralize('type', len(act.types))
        return skill_text

    def grudge_strike_convert(self, act):
        skill_text = 'Deal ' + self.ATTRIBUTES[act.attribute] + ' damage to ' + self.fmt_mass_atk(
            act.mass_attack) + ' depending on HP level (' + fmt_mult(
            act.low_multiplier) + 'x at 1 HP and ' + fmt_mult(act.high_multiplier) + 'x at 100% HP)'
        return skill_text

    def drain_attr_attack_convert(self, act):
        skill_text = 'Deal ' + fmt_mult(act.atk_multiplier) + 'x ATK ' + \
                     self.ATTRIBUTES[act.attribute] + ' damage to ' + self.fmt_mass_atk(act.mass_attack)
        if act.recover_multiplier == 1:
            skill_text += ' and recover the amount as HP'
        else:
            skill_text += ' and recover ' + \
                          fmt_mult(act.recover_multiplier * 100) + '% of the damage as HP'
        return skill_text

    def attribute_change_convert(self, act):
        return 'Change own Att. to ' + \
               self.ATTRIBUTES[act.attribute] + ' for ' + str(act.duration) + ' turns'

    def multi_hit_laser_convert(self, act):
        return 'Deal ' + '{:,}'.format(act.damage) + ' damage to ' + \
               self.fmt_mass_atk(act.mass_attack)

    def hp_nuke_convert(self, act):
        return "Deal {} damage equal to {}x of team's total HP to {}".format(self.ATTRIBUTES[act.attribute],
                                                                             fmt_mult(act.multiplier),
                                                                             self.fmt_mass_atk(act.mass_attack))

    def fixed_pos_convert(self, act):
        return self.fixed_shape_convert(act.pos_map, self.ATTRIBUTES[act.attribute] + ' orb', act)

    def fixed_shape_convert(self, board, orb, act):
        board = deepcopy(board)

        orb_count = 0
        for row_num in board:
            orb_count += len(row_num)
        orb = pluralize(orb, orb_count)

        if board == [[], [], [], [], []]:
            return ''
        elif board == [[5], [], [], [], []]:
            return 'Create one {} in the top-right corner'.format(orb)
        elif board == [[3, 4, 5], [3, 5], [5], [5], []]:
            return 'Create a 7-shape of {} in the upper right corner'.format(orb)
        elif board == [[0, 5], [], [], [], [0, 5]]:
            return 'Create 4 {} at the corners of the board'.format(orb)
        elif board == [[0, 1, 2], [0, 1, 2], [], [], []]:
            return 'Create a 3x2 rectangle of {} in the upper left corner'.format(orb)
        elif board == [[], [1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4], []]:
            return 'Change all positions except for the outer ring to {}'.format(orb)
        elif board == [[2, 3, 4], [1, 4, 5], [5], [1, 4, 5], [2, 3, 4]]:
            return 'Create 13 {} in the shape of a crescent moon.'.format(orb)
        elif board == [[0, 1, 2, 3, 4, 5], [0, 5], [0, 5], [0, 5], [0, 1, 2, 3, 4, 5]]:
            return 'Change the outermost positions of the board to {}'.format(orb)
        elif board == [[4, 5], [3, 4], [2, 3], [1, 2], [0, 1]]:
            return 'Create a 2-orb wide bottom-left to top-right diagonal of {}'.format(orb)
        elif board == [[], [], [1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4]]:
            return 'Create a 3x4 rectangle of {} in the bottom center of the board'.format(orb)
        elif board == [[0, 1, 2, 3, 4], [3], [2], [1], [0, 1, 2, 3, 4]]:
            return 'Create 13 {} in the shape of a Z.'.format(orb)

        if set(sum(board, [])) - {0, 1, 2, 3, 4, 5}:
            print(board)
            return ''

        skill_text = ''
        output = []
        if not (orb_count % 5):
            for row_num in range(1, len(board) - 1):  # Check for cross
                if len(board[row_num]) == 3 and len(board[row_num - 1]) == \
                        len(board[row_num + 1]) == 1:  # Check for cross
                    row_pos = row_num
                    col_pos = board[row_num][1]
                    shape = 'cross'
                    result = (shape, row_pos, col_pos)
                    output.append(result)
                    del board[row_num][1]
            for row_num in range(0, len(board)):  # Check for L
                if len(board[row_num]) == 3:
                    row_pos = row_num
                    if row_num < 2:
                        col_pos = board[row_num + 1][0]
                        del board[row_num + 1][0]
                    elif row_num > 2:
                        col_pos = board[row_num - 1][0]
                        del board[row_num - 1][0]
                    elif len(board[row_num + 1]) > 0:
                        col_pos = board[row_num + 1][0]
                        del board[row_num + 1][0]
                    else:
                        col_pos = board[row_num - 1][0]
                        del board[row_num - 1][0]

                    shape = 'L shape'
                    result = (shape, row_pos, col_pos)
                    output.append(result)

        if not (orb_count % 9):
            for row_num in range(1, len(board) - 1):  # Check for square
                if len(board[row_num]) == len(board[row_num - 1]) == len(board[row_num + 1]) == 3:
                    row_pos = row_num
                    col_pos = board[row_num][1]
                    shape = 'square'
                    result = (shape, row_pos, col_pos)
                    output.append(result)
                    del board[row_num][1]

        if output:
            for entry in output:
                if skill_text:
                    skill_text += '; '
                skill_text += 'Create {} of {} with its center at {} and {}'.format(indef_article(entry[0]),
                                                                                    orb,
                                                                                    ROW_INDEX[entry[1]],
                                                                                    COLUMN_INDEX[entry[2]])
        else:  # Check for row or col
            cols = []
            rows = []
            for col_num in range(6):  # Check for column
                if all(col_num in row for row in board):
                    cols.append(OrbLine(col_num, orb))
            for row_num in range(5):  # Check for column
                if len(board[row_num]) == 6:
                    rows.append(OrbLine(row_num, orb))
            if cols:
                skill_text = self._line_change_convert(cols, COLUMN_INDEX)
            elif rows:
                skill_text = self._line_change_convert(rows, ROW_INDEX)

        if not skill_text:
            board_repr = '\n'.join(''.join(['O' if n in row else 'X' for n in range(6)]) for row in board)
            human_fix_logger.error(
                'Unknown board shape in {} ({}):\n{} \n{}\n{}'.format(
                    act.name, act.skill_id, act.raw_description, board_repr, board))

        return skill_text

    def match_disable_convert(self, act):
        return 'Reduce unable to match orbs effect by {:s}'.format(noun_count('turn', act.duration))

    def board_refresh(self, act):
        return 'Replace all orbs'

    def leader_swap(self, act):
        return 'Becomes Team leader; changes back when used again'

    def unlock_all_orbs(self, act):
        return 'Unlock all orbs'

    def unlock_board_path_toragon(self, act):
        return 'Unlock all orbs; Change all orbs to Fire, Water, Wood, and Light orbs; Show path to 3 combos'

    def random_skill(self, act):
        random_skills_text = []
        for idx, s in enumerate(act.child_skills, 1):
            random_skills_text.append('{}) {}'.format(idx, s.templated_text(self)))
        return 'Activate a random skill from the list: {}'.format(self.concat_list_and(random_skills_text))

    def change_monster(self, act):
        # TODO: Use a template here
        return f"Change to [{next(iter(act.transform_ids))}] for the duration of the dungeon"

    def random_change_monster(self, act):
        if all(count == 1 for count in act.transform_ids.values()):
            mons = self.concat_list_and((f'[{mid}]' for mid in set(act.transform_ids)), conj='or')
        else:
            denom = sum(act.transform_ids.values())
            mons = self.concat_list_and((f'[{mid}] ({Fraction(numer, denom)} chance)'
                                         for mid, numer in sorted(act.transform_ids.items())), conj='or')
        return f"Randomly change to {mons} for the duration of the dungeon"

    def skyfall_lock(self, act):
        attrs = self.attributes_to_str(act.orbs) if act.orbs else 'all'
        return self.fmt_duration(act.duration) + attrs + " orbs appear locked"

    def spawn_spinner(self, act):
        if act.random_count:
            return 'Create {:s} that {:s} every {:.1f}s for {:s}' \
                .format(noun_count('spinner', act.random_count), pluralize("change", act.random_count, verb=True),
                        act.speed, noun_count('turn', act.turns))
        else:
            return self.fixed_shape_convert(act.pos_map, 'spinner', act)

    def ally_active_disable(self, turns: int):
        return 'Disable team active skills for {:s}'.format(noun_count('turn', turns))

    def ally_active_delay(self, turns: int):
        return 'Self-delay active skills by {:s}'.format(noun_count('turn', turns))

    def create_unmatchable(self, act):
        skill_text = self.fmt_duration(act.duration)
        if act.orbs:
            skill_text += self.concat_list_and(self.ATTRIBUTES[i] for i in act.orbs) + ' '
        return skill_text + "orbs are unmatchable"

    def conditional_hp_thresh(self, act):
        if act.lower_limit == 0:
            return f"If HP <= {act.upper_limit}%: "
        if act.upper_limit == 100:
            return f"If HP >= {act.lower_limit}%: "
        return f"If HP is bewteen {act.lower_limit}% and {act.upper_limit}%: "

    def nail_orb_skyfall(self, act):
        return f"{self.fmt_duration(act.duration)}+{fmt_mult(act.chance * 100)}% chance for nail orb skyfall"

    def lead_swap_sub(self, act):
        return f"Swap team leader with the sub in the {ordinal(act.sub_slot)} position"

    def composition_buff(self, act):
        if act.attributes and act.types:
            human_fix_logger.warning(f"Can't parse active skill {act.skill_id}: attributes and types.")
            return ""
        skill_text = (self.fmt_duration(act.duration) + '+' +
                      self.fmt_multiplier_text(0, act.atk_boost, act.rcv_boost, default=0))
        if act.attributes:
            return skill_text + f" for each {self.fmt_multi_attr(act.attributes)} card in team"
        else:
            return skill_text + f" for each instance of {self.typing_to_str(act.types, 'or')} in team"

    def team_target_stat_change(self, act):
        skill_text = self.fmt_duration(act.duration) + self.fmt_multiplier_text(1, act.atk_mult, 1)
        targets = []
        if act.target & 1:
            targets.append("this monster")

        if act.target & 6 == 6:
            targets.append("both leaders")
        elif act.target & 2:
            targets.append("team leader")
        elif act.target & 4:
            targets.append("friend leader")

        if act.target & 8:
            targets.append("all subs")

        if act.target & 15 == 15:
            targets = ["all monsters"]

        if act.target & ~15:
            human_fix_logger.warning(f"Can't parse active skill {act.skill_id}: Unknown target {act.target}")
            targets.append("???")
        return skill_text + " for " + self.concat_list_and(targets)

    def evolving_active(self, act):
        skill_text = "After each skill, evolve to the next:"
        for c, skill in enumerate(act.child_skills, 1):
            skill_text += f" {c}) {skill.templated_text(self)}"
        return skill_text

    def looping_evolving_active(self, act):
        skill_text = "After each skill, evolve to the next looping around if the end is reached:"
        for c, skill in enumerate(act.child_skills, 1):
            skill_text += f" {c}) {skill.templated_text(self)}"
        return skill_text

    def conditional_floor_thresh(self, act, context):
        if act.lower_limit == 0:
            skill_text = f" on floor {act.upper_limit} or earlier: "
        elif act.upper_limit == 9999:
            skill_text = f" on floor {act.lower_limit} or later: "
        else:
            skill_text = f" between floor {act.lower_limit} and floor {act.upper_limit} (inclusive): "

        if context is None or context.index(act) != 0:
            # Context-less or not first
            return "If" + skill_text
        else:
            # First
            if act.lower_limit == 0:
                return "Must be used" + skill_text
            elif act.upper_limit == 9999:
                return "Can only be used" + skill_text
            else:
                return "Must (and can only) be used" + skill_text

    def changeto7x6board(self, act):
        return self.fmt_duration(act.duration) + "the board becomes 7x6"

    def inflict_es(self, act):
        if act.selector_type == 2:
            if len(act.players) == 1:
                skill_text = f"To the player in the {ordinal(act.players[0])} place, "
            else:
                skill_text = f"To the players in the {self.concat_list_and(map(ordinal, act.players))} places, "
        elif act.selector_type == 3:
            skill_text = "To all players higher ranked than you, "
        else:
            human_fix_logger.warning(f"Invalid AS 1000 selector_type: {act.selector_type}")
            skill_text = "To some other players, "
        # TODO: Add a template here
        return skill_text + "do something mean (probably)"

    def multi_part_active(self, act):
        text_to_item = OrderedDict()
        for p in act.parts:
            if p.needs_context:
                p_text = p.text(self, act.parts)
            else:
                p_text = p.text(self)
            if p_text in text_to_item:
                text_to_item[p_text].repeat += 1
            else:
                text_to_item[p_text] = PartWithTextAndCount(p, p_text)

        return self.combine_skills_text(list(text_to_item.values()))

    def combine_skills_text(self, skills: List[PartWithTextAndCount]):
        skill_text = ""
        for c, skillpart in enumerate(skills):
            skill_text += skillpart.templated_text(self)
            if c != len(skills) - 1 and not isinstance(skillpart.act, ASConditional):
                skill_text += '; '
        return skill_text

    def cloud(self, act):
        if act.cloud_width == 6 and act.cloud_height == 1:
            shape = 'row'
        elif act.cloud_width == 1 and act.cloud_height == 5:
            shape = 'column'
        else:
            shape = '{:d}×{:d}'.format(act.cloud_width, act.cloud_height)
            shape += ' square' if act.cloud_width == act.cloud_height else ' rectangle'
        pos = []
        if act.origin_x is not None and shape != 'row':
            pos.append('{:s} row'.format(ordinal(act.origin_x)))
        if act.origin_y is not None and shape != 'column':
            pos.append('{:s} column'.format(ordinal(act.origin_y)))
        if len(pos) == 0:
            pos.append('a random location')
        return 'A {:s} of clouds appears for {:s} at {:s}' \
            .format(shape, noun_count('turn', act.duration), ', '.join(pos))

    def tape(self, act):
        return self.fmt_duration(act.duration) + "seal " + COLUMN_INDEX[act.column - 1]

    def damage_cap_boost(self, act):
        return self.fmt_duration(act.duration) \
               + "this monster damage cap becomes {}".format(act.damage_cap * 1e8)
