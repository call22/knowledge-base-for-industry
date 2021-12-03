from trankit import Pipeline
from elementExtract.common import HpWord
import json

clause_complement = ['ccomp', 'xcomp']
Clauses = ['csubj', 'csubj:pass', 'advcl', 'parataxis', 'conj', 'ccomp', 'xcomp', 'cc']
Objects = ['obj', 'nsubj:pass', 'iobj', 'obl', 'obl:patient', 'dislocated', 'dislocated:vo']
Subjects = ['nsubj', 'obl:agent', 'vocative']
Modificatons = ['nmod', 'appos', 'nummod', 'amod', 'acl', 'acl:relcl']
MainRels = clause_complement + Clauses + Objects + Subjects + Modificatons
negWords = ['不可以', '不允许', '不能够', '不应该', '不可', '不许', '不能', '不得', '不准', '不应']
conditionWords = ['当', '如果', '假如', '假若', '假使', '万一', '要是', '一旦', '只要', '如']


class RuleExtract1:
    def __init__(self):
        self.p = Pipeline('chinese')
        self.words = []
        self.root = None
        self.entities = []
        self.subjects = []
        self.objects = []
        self.requirements = []
        self.bans = []
        self.time = []
        self.locations = []
        self.conditions = []

    def setSent(self, sentence):
        self.sent = sentence
        self.sentences = self.p.posdep(sentence)['sentences']
        self.words = []
        self.root = None
        self.entities = []
        self.subjects = []
        self.objects = []
        self.requirements = []
        self.bans = []
        self.time = []
        self.locations = []
        self.conditions = []

    def parser(self):
        self.words = self._setWords(self.sentences)
        self._addTag(self.root)
        self._extractTag(self.root)

    def __repr__(self):
        out = ''
        for word in self.words:
            if word.head != -2:
                out += word.__repr__() + '\n'
        out += '实体: '
        for e in self.entities:
            out += self.sent[e[0]:e[1]] + '、 '

        out += '\n主语: '
        for e in self.subjects:
            out += self.sent[e[0]:e[1]] + '、 '

        out += '\n宾语: '
        for e in self.objects:
            out += self.sent[e[0]:e[1]] + '、 '

        return out

    def _setWords(self, sentences):
        words = []
        length = 0
        self.root = None
        pre_root = None
        for sent in sentences:
            des = sent['tokens']
            for i in des:
                words.append(
                    HpWord(i['id'] - 1 + length, i['text'], i['deprel'], i['upos'], i['head'] - 1 + length, i['dspan']))
                if i['deprel'] == 'root':
                    if self.root is None:
                        self.root = words[-1]
                    else:
                        words[-1].head = pre_root.id  # 以第一个句子root为root，其余句子为它的child，修改rel标记作为句子分隔
                    pre_root = words[-1]
            length += len(des)

        # 将id和index等价
        for _idx, word in enumerate(words):
            for child_idx, child in enumerate(words):
                if child.head == word.id:
                    word.child.append(child_idx)
        return words

    def _addTag(self, root):
        """
        自顶向下，先序遍历标记
        :param root:
        :return:
        """

        # 找到系动词

        child_set = root.child.copy()
        for child_id in child_set:
            self._addTag(self.words[child_id])
        headW = self.words[root.head]

        # 1. compound 合并
        if root.rel in ['compound']:
            if headW.span[0] == root.span[1] or headW.span[1] == root.span[0]:
                if headW.span[0] == root.span[1]:
                    headW.text = root.text + headW.text
                    headW.span = (root.span[0], headW.span[1])
                    headW.tag.append('entity')
                elif headW.span[1] == root.span[0]:
                    headW.text = headW.text + root.text
                    headW.span = (headW.span[0], root.span[1])
                    headW.tag.append('entity')

                headW.child.extend(root.child)
                for child in root.child:
                    self.words[child].head = headW.id
                headW.child.remove(root.id)
                root.head = -2
        # NOUN且并列时，实体tag
        if root.postag == 'NOUN':
            for _id in root.child:
                if self.words[_id].rel == 'conj':
                    root.tag.append('entity')
                    break
        # 主语tag
        if root.rel in Subjects:
            root.tag.append('subject')
        # 宾语tag
        elif root.rel in Objects:
            root.tag.append('object')
        # 条件tag
        elif root.text in conditionWords and root.postag in ['ADP'] \
                and root.rel in ['case']:
            if headW.postag in ['VERB']:
                headW.tag.append('condition')
                # condition中不能有ban和require
                if 'ban' in headW.tag:
                    headW.tag.remove('ban')
                if 'require' in headW.tag:
                    headW.tag.remove('require')
        # 时间tag
        elif root.rel in ['obl:tmod']:
            root.tag.append('time')
        # 地点tag
        elif root.rel in ['case:loc']:
            headW.tag.append('location')
        # 要求tag
        elif (root.text in ['应该', '必须', '宜', '应'] or len({'应', '须', '需'}.intersection(set(root.text))) > 0) \
                and '不' not in root.text and root.rel in ['aux']:
            if (headW.postag in ['VERB'] or self._find_cop(headW) > -1) \
                    and 'acl' not in headW.rel and 'condition' not in headW.tag:  # 补丁，条件中不能有require
                headW.tag.append('require')
        # 禁止tag TODO:
        else:
            ban_w = None
            if root.text in ['禁止', '严禁'] and root.postag in ['VERB']:  # 【防止】不是关键词
                ban_w = root

            elif root.text in negWords and root.postag in ['AUX'] \
                    and (headW.postag in ['VERB'] or self._find_cop(headW) > -1):  # 考虑系动词
                ban_w = headW

            elif '不' in root.text and root.rel in ['aux', 'advmod'] and \
                    headW.text in ['可以', '能够', '允许', '能', '可']:  # 当’不‘与’可以‘被拆分时
                if self.words[headW.head].postag in ['VERB'] or self._find_cop(self.words[headW.head]) > -1:  # 考虑系动词
                    ban_w = self.words[headW.head]
            if ban_w is not None and 'acl' not in ban_w.rel and 'condition' not in ban_w.tag:  # 补丁，条件中不能有ban
                ban_w.tag.append('ban')

    """标记统计，规则抽取"""

    def _extractTag(self, root):
        """
        自底向上，记录从细粒度到粗粒度的全部内容
        :param root:
        :return:
        """
        child_set = root.child.copy()
        child_set = sorted(child_set)
        for child_id in child_set:
            self._extractTag(self.words[child_id])
        headW = self.words[root.head]

        # combine
        for child_id in child_set:
            if self.words[child_id].rel in Modificatons[:4]:
                self._combine_neg(self.words[child_id], ['case', 'mark', 'punct'])
        self._combine_cond(root, Modificatons[:4])

        # case1：conj且head不为形容词、副词等修饰性词，则继承该tag
        cond = self._find_rel(root)
        if root.rel in ['conj'] and len(headW.tag) > 0 and headW.postag not in ['ADJ', 'ADV']:
            self._merge_tag(root, headW, cond)
        # case2：trankit解析错误情况：电源开关应安装在压力机上或非常接近压力机的位置，并且(安装位置)易于识别和接近。
        if len(cond) > 0:
            # 以父级tag优先
            if root.rel in ['advcl'] and ({'ban', 'require'}.intersection(set(headW.tag))):
                self._merge_tag(root, headW, cond)
            else:
                for child_id in root.child:
                    if self.words[child_id].rel in ['advcl'] \
                            and ({'ban', 'require'}.intersection(set(self.words[child_id].tag))):
                        self._merge_tag(root, self.words[child_id], cond)

        # entity记录
        if 'entity' in root.tag:
            self.entities.append(root.span)
        # subject记录
        elif 'subject' in root.tag:
            tmp = root.span if root.postag not in ['VERB'] else self._root_span(root.span, self._span_text(root))
            # self.subjects.append(root.span)
            self.subjects.append(tmp)
        # object记录
        elif 'object' in root.tag:
            tmp = root.span if root.postag not in ['VERB'] else self._root_span(root.span, self._span_text(root))
            self.objects.append(tmp)

        # time 记录
        elif 'time' in root.tag:
            for child_id in child_set:
                if self.words[child_id].rel in Modificatons:
                    self._combine_neg(self.words[child_id], ['case', 'mark', 'punct'])
            self._combine_cond(root, Modificatons)
            self.time.append(root.span)

        # location 记录
        elif 'location' in root.tag:
            for child_id in child_set:
                if self.words[child_id].rel in Modificatons:
                    self._combine_neg(self.words[child_id], ['case', 'mark', 'punct'])
            self._combine_cond(root, Modificatons)
            self.locations.append(root.span)

        # condition，ban，require 记录 ;不合并节点，只收集span
        elif len({'condition', 'ban', 'require'}.intersection(set(root.tag))) == 1:
            # 不合并subject,condition,ban,require
            span_list = []
            for child_id in root.child:
                child = self.words[child_id]
                if len({'subject', 'condition', 'ban', 'require'}.intersection(
                        set(child.tag))) == 0 and child.rel not in ['root']:
                    span_list.extend(self._span_text(child))
            span_list.append(root.span)

            root_span = self._root_span(root.span, span_list)
            if 'condition' in root.tag:
                self.conditions.append(root_span)
            elif 'ban' in root.tag:
                self.bans.append(root_span)
            elif 'require' in root.tag:
                self.requirements.append(root_span)

    def genViewVer(self):
        """
        将condition、ban、require直接转为文字
        :return: str
        """
        return [{
            'subject': self.subjects,
            'object': self.objects,
            'entity': self.entities,
            'condition': self.conditions,
            'ban': self.bans,
            'require': self.requirements
        }]

    def genAppVer(self):
        # 8. ban 记录 #TODO: atom:<entity>,<verb>; relation:<AND>, <OR>, <MOD>;
        #  TODO: attribute:<condition>, <subject>, <object>, <ban>, <require>, <time>, <location>,
        #  TODO: <set>: 集合，无其他含义，与relation一同出现
        return []
        # 合并两个child，成功True，失败False

    def _find_cop(self, w):
        for _i in w.child:
            if self.words[_i].rel in ['cop'] and self.words[_i].postag in ['VERB']:
                return _i
        return -1

    def _combine_child(self, c1, c2):
        _child = self.words[c2]
        if c1 != -1 and self.words[c1].span[1] == _child.span[0]:
            last_child = self.words[c1]
            _child.text = last_child.text + _child.text
            _child.span = (last_child.span[0], _child.span[1])
            _child.child.extend(last_child.child)
            for _i in last_child.child:
                self.words[_i].head = _child.id

            _w = self.words[_child.head]
            _w.child.remove(c1)
            last_child.head = -2
            return True
        return False

    # 将child合并到root中，成功True，失败False
    def _combine_root(self, c, r):
        _child = self.words[c]
        _w = self.words[r]
        if _child.span[0] == _w.span[1] or _child.span[1] == _w.span[0]:
            if _child.span[0] == _w.span[1]:
                _w.text = _w.text + _child.text
                _w.span = (_w.span[0], _child.span[1])
            elif _child.span[1] == _w.span[0]:
                _w.text = _child.text + _w.text
                _w.span = (_child.span[0], _w.span[1])
            _w.child.extend(_child.child)
            for _i in _child.child:
                self.words[_i].head = _w.id
            _w.child.remove(_child.id)
            _child.head = -2
            return True
        return False

    # 合并rel不满足条件的节点
    def _combine_neg(self, w, _relations):  # 合并不在_relations中的关联
        last_id = -1
        w.child = sorted(w.child)
        _children = w.child.copy()
        for _id in _children:
            _child = self.words[_id]
            self._combine_neg(_child, _relations)
            if _child.rel not in _relations:
                # combine children
                self._combine_child(last_id, _id)
                last_id = _id
                # combine child to w
                f = self._combine_root(_id, w.id)
                if f:
                    last_id = -1

    # 合并rel满足条件的节点
    def _combine_cond(self, w, _relations):
        last_id = -1
        w.child = sorted(w.child)
        _children = w.child.copy()
        for _id in _children:
            _child = self.words[_id]
            self._combine_cond(_child, _relations)
            if _child.rel in _relations:
                # combine children
                self._combine_child(last_id, _id)
                last_id = _id
                # combine child to w
                f = self._combine_root(_id, w.id)
                if f:
                    last_id = -1

    def _find_rel(self, w):  # OR与AND关系
        for _i in w.child:  # TODO: 与或关系还要细化
            if self.words[_i].text in ['并且', '和', '与', '同', '且'] and self.words[_i].rel in ['cc', 'mark']:
                return ['AND']
            if self.words[_i].text in ['、', '或', '或者', '及', '以及'] and self.words[_i].rel in ['cc', 'mark']:
                return ['OR']
        return []

    # 返回w子树的所有word span
    def _span_text(self, w):
        _list = []
        for _id in w.child:
            _list.extend(self._span_text(self.words[_id]))
        _list.append(w.span)
        return _list

    @staticmethod
    # 将target的tag扩充
    def _merge_tag(target, source, flag):
        target.tag.extend(source.tag)
        target.tag.extend(flag)
        target.tag = list(set(target.tag))

    @staticmethod
    # 返回root和子树的已合并span list中，root对应span
    def _root_span(w_span, spans):
        spans = sorted(spans, key=lambda x: x[0])
        new_list = [(-1, -1)]
        for _idx in range(len(spans)):
            if new_list[-1][1] == spans[_idx][0]:
                new_list[-1] = (new_list[-1][0], spans[_idx][1])
            else:
                new_list.append(spans[_idx])
        new_list.pop(0)

        for _idx in range(len(new_list)):
            if new_list[_idx][0] <= w_span[0] and w_span[1] <= new_list[_idx][1]:
                return new_list[_idx]


if __name__ == '__main__':
    ruleExt = RuleExtract1()
    s = ["高速轴联轴器、低速轴联轴器、制动轮、制动盘及液力偶合器都应加装防护罩。当驱动装置设置在地面或人员能接近的平台上且带速大于3.15m/s时，整个驱动装置范围应采用高度不低于1500mm的护栏予以防护。",
         '当管道采用管沟方式敷设时，管沟与泵房、灌桶间、罐组防火堤、覆土油罐室的结合处，不应设置密闭隔离墙。',
         '电气遥控或可移式脚控操纵装置，应安放在不影响自由活动的工作场所。电气遥控踏板或按钮的安装位置必须考虑到当踏压动作时，不使操作者进入危险区。可移式踏杆，当使用时必须固定在操纵杆上并与其联动，当不使用时应能被拆除。',
         "液压机必须具有防止柱塞(或滑块)超过工作行程的限位装置，除机械限位装置或机构外，液压控制系统中应有电器或液压或两者兼有的限位保险装置。",
         "大型压力机各个立柱应设置急停按钮，按钮应具有自锁功能。急停按钮应设置在控制点、给料点附近，人手可迅速触及且不会产生误动作之处。", "操纵装置必须安装正确、牢固，不应采用机械式刚性脚踏杠杆操纵机构。",
         '电源开关应安装在压力机上或非常接近压力机的位置，并且易于识别和接近。',
         '下列储罐的通气管上必须装设阻火器：1. 储存甲B类、乙类、丙A类液体的固定顶储罐和地上卧式储罐。2. 储存甲B类和乙类液体的覆土卧式油罐。3. 储存甲B类、乙类、丙A类液体并采用氮气密封保护系统的内浮顶储罐。']
    for sent in s:
        ruleExt.setSent(sent)
        ruleExt.parser()
        view_json = ruleExt.genViewVer()[0]
        print(sent)
        print('=' * 30)
        for key in view_json.keys():
            print(str(key) + ':')
            v_text = ''
            for item in view_json[key]:
                v_text += sent[item[0]:item[1]] + ' | '
            print(v_text)
        print('=' * 30)
    # print(ruleExt)
