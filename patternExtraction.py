import re


class PatternExtraction:
    def __init__(self):
        self.but_wds = self.pattern_but()
        self.seq_wds = self.pattern_seq()
        self.condition_wds = self.pattern_condition()
        self.causality_wds = self.pattern_causality()

    '''转折事件'''

    def pattern_but(self):
        wds = [
            [['就算是', '固然', '即便'], ['也', '还', '却']],
            [['虽然', '纵然', '尽管', '即使', '虽说', '虽'], ['但是', '然而', '仍然', '可是', '还是', '也', '还', '但', '可', '却']],
            [['不是'], ['而是']],
            [['宁愿', '宁肯', '宁可', '不管', '不论', '无论'], ['也不', '决不', '也要']],
            [['无论'], ['仍然', '始终', '都', '也', '还',  '总', '一直']],
            [['与其'], ['宁可', '不如', '宁肯', '宁愿']]]

        return wds

    '''顺承事件'''

    def pattern_seq(self):
        wds = [
            [['首先', '先是', '第一'], ['其次', '然后', '再', '又', '还', '才']],
            [['一方面'], ['另一方面']],
            [['不但', '不仅', '不单', '不光', '不只'], ['而且', '并且', '也', '还']],
            [['或是', '要么', '或者'], ['或是',  '要么', '或者']],
            [[], ['接下来', '进而', '之后', '然后', '后来', '接着', '随后', '其次', '而且', '并且', '也', '还']],
        ]
        return wds

    '''条件事件'''

    def pattern_condition(self):
        wds = [
            [['除非', '只有'], ['否则', '才', '不然', '要不']],
            [['既然'], ['又', '且', '也', '亦']],
            [['假如', '假若', '如果', '假使', '万一', '要是', '一旦', '只要', '如'], ['那么', '就', '那', '则', '便']],
        ]
        return wds

    '''因果事件'''

    def pattern_causality(self):
        wds = [[['因为', '由于'], ['从而', '为此', '因而', '致使', '以致于?', '以至于?', '所以', '于是', '故', '故而', '因此']],
               [['之所以'], ['是因为', '是由于', '是缘于']],
               [[], ['以致于?', '以至于?', '致使', '导致', '促成', '造成', '促使', '引发', '引起', '致使', '使得', '诱使', '从而', '为此', '因而', '致使',
                     '所以', '于是', '故', '故而', '因此']],
               ]
        return wds

    '''编译模式'''

    def create_pattern2(self, wds):
        patterns = []
        for wd in wds:
            pre = wd[0]
            pos = wd[1]
            pattern = re.compile(
                '({0})(.*?)({1})(.*?)'.format('|'.join(pre), '|'.join(pos)))
            patterns.append(pattern)
        return patterns

    '''模式匹配'''

    def pattern_match_Rel(self, patterns: list, sent, wds, type):
        # 返回关联词所在位置
        result = []
        for i, p in enumerate(patterns):
            res = p.split(sent)
            pre = -1
            for j, fragment in enumerate(res):
                if fragment in wds[i][0]:
                    pre = j
                elif fragment in wds[i][1]:
                    if pre == -1:   # 没有pre的情况
                        p = -1
                        for k in res[:j]:
                            p += len(k)
                        q = p + len(fragment) + 1
                        p -= 3  # ’可能会造成‘去除’可能会‘情况
                        if sent[p] in "？?！!。；;：:,，":
                            p -= 1
                        if p < 0:
                            p = 0

                        result.append([type, p, q])
                    else:
                        p = 0
                        for k in res[:pre+1]:
                            p += len(k)
                        q = 0
                        for k in res[:j+1]:
                            q += len(k)
                        result.append([type, p+1, q+1])
                        pre = -1

        return result

    def add_relation(self, sent):
        self.causality_patterns2 = self.create_pattern2(self.causality_wds)
        self.but_patterns2 = self.create_pattern2(self.but_wds)
        self.seq_patterns2 = self.create_pattern2(self.seq_wds)
        self.condition_patterns2 = self.create_pattern2(self.condition_wds)

        rels = []
        rels.extend(self.pattern_match_Rel(self.causality_patterns2, sent, self.causality_wds, 'Cause'))
        rels.extend(self.pattern_match_Rel(self.but_patterns2, sent, self.but_wds, 'But'))
        rels.extend(self.pattern_match_Rel(self.condition_patterns2, sent, self.condition_wds, 'Condition'))
        rels.extend(self.pattern_match_Rel(self.seq_patterns2, sent, self.seq_wds, 'Seq'))
        return rels
