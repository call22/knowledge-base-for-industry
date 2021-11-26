from trankit import Pipeline
from xml.etree import ElementTree as etree
from xml.dom import minidom as minidom
from common import HpWord

clause_complement = ['ccomp', 'xcomp']
Clauses = ['csubj', 'csubj:pass', 'advcl', 'parataxis', 'conj', 'ccomp', 'xcomp', 'cc']
Objects = ['obj', 'nsubj:pass', 'iobj', 'obl', 'obl:patient', 'dislocated', 'dislocated:vo']
Subjects = ['nsubj', 'obl:agent', 'vocative']
Modificatons = ['nmod', 'appos', 'nummod', 'amod', 'acl', 'acl:relcl']
MainRels = clause_complement + Clauses + Objects + Subjects + Modificatons


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
        self.xml = etree.Element('rule')

    def setSent(self, sentence):
        self.sent = sentence
        self.sentences = self.p.posdep(sentence)['sentences']

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
        child_set = root.child.copy()
        for child_id in child_set:
            self._addTag(self.words[child_id])

        # 1. compound 合并
        if root.rel in ['compound']:
            _head = self.words[root.head]
            if _head.span[0] == root.span[1] or _head.span[1] == root.span[0]:
                if _head.span[0] == root.span[1]:
                    _head.text = root.text + _head.text
                    _head.span = (root.span[0], _head.span[1])
                    _head.tag.append('entity')
                elif _head.span[1] == root.span[0]:
                    _head.text = _head.text + root.text
                    _head.span = (_head.span[0], root.span[1])
                    _head.tag.append('entity')

                _head.child.extend(root.child)
                for child in root.child:
                    self.words[child].head = _head.id
                _head.child.remove(root.id)
                root.head = -2
        # NOUN且并列时
        if root.postag == 'NOUN':
            for _id in root.child:
                if self.words[_id].rel == 'conj':
                    root.tag.append('entity')
                    break
        # 2. 主语tag
        if root.rel in Subjects:
            root.tag.append('subject')
        # 3. 宾语tag
        if root.rel in Objects:
            root.tag.append('object')
        # 4. 要求tag
        if root.text in ['应该', '必须', '宜', '应'] and root.rel in ['aux']:
            _head = self.words[root.head]
            if _head.postag in ['VERB']:
                _head.tag.append('require')
        # 5. 禁止tag
        if root.text in ['禁止', '严禁', '防止'] and root.postag in ['VERB']:
            root.tag.append('ban')

        if '不' in root.text and root.rel in ['aux', 'advmod']:
            _head = self.words[root.head]
            if _head.postag in ['VERB']:
                _head.tag.append('ban')
        # 6. 条件tag
        if root.text in ['当', '如果', '假如', '假若', '假使', '万一', '要是', '一旦', '只要', '如'] and root.postag in ['ADP'] \
                and root.rel in ['case']:
            _head = self.words[root.head]
            if _head.postag in ['VERB']:
                _head.tag.append('condition')

        # 7. 时间tag
        if root.rel in ['obl:tmod']:
            root.tag.append('time')
        # 8. 地点tag
        if root.rel in ['case:loc']:
            _head = self.words[root.head]
            _head.tag.append('location')

    """标记统计，规则抽取"""

    def _extractTag(self, root):
        """
        自底向上，记录从细粒度到粗粒度的全部内容
        :param root:
        :return:
        """
        child_set = root.child.copy()
        sorted(child_set)
        for child_id in child_set:
            self._extractTag(self.words[child_id])

        # 1. entity记录
        if 'entity' in root.tag:
            self.entities.append(root.span)

        # 合并两个child，成功True，失败False
        def _combine_child(c1, c2):
            child = self.words[c2]
            if c1 != -1 and self.words[c1].span[1] == child.span[0]:
                last_child = self.words[c1]
                child.text = last_child.text + child.text
                child.span = (last_child.span[0], child.span[1])
                child.child.extend(last_child.child)
                for _i in last_child.child:
                    self.words[_i].head = child.id

                _w = self.words[child.head]
                _w.child.remove(c1)
                last_child.head = -2
                return True
            return False

        # 将child合并到root中，成功True，失败False
        def _combine_root(c, r):
            child = self.words[c]
            _w = self.words[r]
            if child.span[0] == _w.span[1] or child.span[1] == _w.span[0]:
                if child.span[0] == _w.span[1]:
                    _w.text = _w.text + child.text
                    _w.span = (_w.span[0], child.span[1])
                elif child.span[1] == _w.span[0]:
                    _w.text = child.text + _w.text
                    _w.span = (child.span[0], _w.span[1])
                _w.child.extend(child.child)
                for _i in child.child:
                    self.words[_i].head = _w.id
                _w.child.remove(child.id)
                child.head = -2
                return True
            return False

        # 合并rel不满足条件的节点
        def _combine_neg(w, _relations):  # 合并不在_relations中的关联
            last_id = -1
            sorted(w.child)
            _children = w.child.copy()
            for _id in _children:
                child = self.words[_id]
                _combine_neg(child, _relations)
                if child.rel not in _relations:
                    # combine children
                    _combine_child(last_id, _id)
                    last_id = _id
                    # combine child to w
                    f = _combine_root(_id, w.id)
                    if f:
                        last_id = -1

        # 合并rel满足条件的节点
        def _combine_cond(w, _relations):
            last_id = -1
            sorted(w.child)
            _children = w.child.copy()
            for _id in _children:
                child = self.words[_id]
                _combine_cond(child, _relations)
                if child.rel in _relations:
                    # combine children
                    _combine_child(last_id, _id)
                    last_id = _id
                    # combine child to w
                    f = _combine_root(_id, w.id)
                    if f:
                        last_id = -1

        # 2. combine
        for child_id in child_set:
            if self.words[child_id].rel in Modificatons[:4]:
                _combine_neg(self.words[child_id], ['case', 'mark', 'punct'])
        _combine_cond(root, Modificatons[:4])

        # 3. conj若head为subject，object，则继承该tag
        if root.rel in ['conj'] and len(self.words[root.head].tag) > 0:
            root.tag.extend(self.words[root.head].tag)
            root.tag = list(set(root.tag))

            def _find_rel(w):  # OR与AND关系
                for i in w.child:  # TODO: 与或关系还要细化
                    if self.words[i].text in ['和', '与', '同', '且']:
                        return ['AND']
                    if self.words[i].text in ['、', '或', '或者', '及', '以及']:
                        return ['OR']
                return []

            root.tag.extend(_find_rel(root))

        # 4. subject，object记录
        if 'subject' in root.tag:
            self.subjects.append(root.span)
        if 'object' in root.tag:
            self.objects.append(root.span)

        # 5. time 记录
        if 'time' in root.tag:
            for child_id in child_set:
                if self.words[child_id].rel in Modificatons:
                    _combine_neg(self.words[child_id], ['case', 'mark', 'punct'])
            _combine_cond(root, Modificatons)
            self.time.append(root.span)

        # 6. location 记录
        if 'location' in root.tag:
            for child_id in child_set:
                if self.words[child_id].rel in Modificatons:
                    _combine_neg(self.words[child_id], ['case', 'mark', 'punct'])
            _combine_cond(root, Modificatons)
            self.locations.append(root.span)

        # 7. condition 记录 #TODO: 先直接combine
        # 8. ban 记录 #TODO: atom:<entity>,<verb>; relation:<AND>, <OR>, <MOD>;
        #  TODO: attribute:<condition>, <subject>, <object>, <ban>, <require>, <time>, <location>,
        #  TODO: <set>: 集合，无其他含义，与relation一同出现

    def _genXML(self, root, x_root):
        """
        语法树转为xml形式，自顶向下，先序遍历
        :param root: 语法树根节点
        :param x_root: xml根节点
        :return:
        """
        # atom
        if 'entity' in root.tag:
            entity = etree.SubElement(x_root, 'entity')
            entity.text = root.text
        elif 'time' in root.tag:
            time = etree.SubElement(x_root, 'time')
            time.text = root.text
        elif 'location' in root.tag:
            location = etree.SubElement(x_root, 'location')
            location.text = root.text

        # combination
        elif 'subject' in root.tag:
            subject = etree.SubElement(x_root, 'subject')
        elif 'object' in root.tag:
            object = etree.SubElement(x_root, 'object')
        elif 'condition' in root.tag:
            condition = etree.SubElement(x_root, 'condition')
        elif 'ban' in root.tag:
            ban = etree.SubElement(x_root, 'ban')
        elif 'require' in root.tag:
            require = etree.SubElement(x_root, 'require')
        elif len(root.tag) == 0:
            pass


if __name__ == '__main__':
    ruleExt = RuleExtract1()
    s = "高速轴联轴器、低速轴联轴器、制动轮、制动盘及液力偶合器都应加装防护罩。当驱动装置设置在地面或人员能接近的平台上且带速大于3.15m/s时，整个驱动装置范围应采用高度不低于1500mm的护栏予以防护。"
    # s = '当管道采用管沟方式敷设时，管沟与泵房、灌桶间、罐组防火堤、覆土油罐室的结合处，不应设置密闭隔离墙。'
    ruleExt.setSent(s)
    ruleExt.parser()
    print(ruleExt)
