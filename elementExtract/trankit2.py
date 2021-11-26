from trankit import Pipeline
from common import HpSent, HpWord, RelConstruct
from patternExtraction import PatternExtraction
import re

'''中文复句整理及模板'''
# 拆分句子为 主语、宾语、从句、补句
clause_complement = ['ccomp', 'xcomp']
Clauses = ['csubj', 'csubj:pass', 'advcl', 'parataxis', 'conj', 'ccomp', 'xcomp', 'cc']
Objects = ['obj', 'nsubj:pass', 'iobj', 'obl', 'obl:patient']
Subjects = ['nsubj', 'obl:agent', 'vocative', 'dislocated', 'dislocated:vo']

# 拆分句子为 实体、操作、关联关系
Entity = ['compound']
Relation = []
Operation = []


# input sentences, output Result
class Trankit2Parser:
    def __init__(self, s=''):
        self.p = Pipeline('chinese')
        self.words = []
        self.root = None
        self.events = []
        if s != '':
            self.setSent(s)

    def setSent(self, sentence):
        self.sent = sentence
        self.sentences = self.p.posdep(sentence)['sentences']

    """基于规则的事件抽取"""

    def extractEvents(self, root):
        # extract Events: 事件按照句子中出现的先后排列，事件id与index同步
        events, _ = self.__extractEvents(root)
        events = sorted(events, key=lambda x: x.id)
        # 合并id相同的event（subject不同, object不同）
        temp_events = []
        for i, event in enumerate(events):
            if i > 0 and events[i - 1].id == event.id:
                temp_events[-1].subject.extend(event.subject)
                temp_events[-1].subject = sorted(set(temp_events[-1].subject), key=lambda x: x.id)
                temp_events[-1].object.extend(event.object)
                temp_events[-1].object = sorted(set(temp_events[-1].object), key=lambda x: x.id)
            else:
                temp_events.append(event)
        events = temp_events
        # 事件head与id同步
        id_set = [-1]
        for e in events:
            id_set.append(e.id)
        for e in events:
            if e.head in id_set:
                continue

            def _find_super(id):
                if id in id_set:
                    return id
                else:
                    return _find_super(self.words[id].head)

            e.head = _find_super(e.head)
        # 将id与index同步
        for _idx, event in enumerate(events):
            for _ch_idx, _child in enumerate(events):
                if _child.head == event.id:  # 寻找上级
                    event.child.append(_ch_idx)
                    _child.head = _idx
            event.id = _idx
        return events

    """要素和结构抽取，最终输出句子要素以及要素之间的结构"""

    def extractRelConstruct(self):
        result = RelConstruct()
        self.events = self.extractEvents(self.root)
        # self.events = self.__splitEvents(self.events)
        result.entities, result.subEventRels = self.__LogoEntitySubevent(self.events)
        result.relations = self.__LogoRelation(result)
        result.sentence = self.sent
        return result

    def parser(self):
        # 多句子合并根节点前后连接为链条
        self.words = self._setWords(self.sentences)
        # 从树中提取
        result = self.extractRelConstruct()
        return result

    def __repr__(self):
        return '\n'.join(map(str, self.words))

    """合并多个句子的words"""

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

# TODO: 提取实体，同时标记关系
    def __extractEvents(self, root, already_set=None):
        """
        后序遍历，提取事件短语，并记录关系，同时修改words为森林
        :param root: words的根节点
        :return:
        """

        def removeParent(word):
            if word.head != -1:
                self.words[word.head].child.remove(word.id)
                self.words[word.id].head = -1

        if already_set is None:
            already_set = set()
        events = []
        child_set = root.child.copy()  # 会修改root.child，故浅拷贝
        for _child_id in child_set:
            _event, already_set = self.__extractEvents(self.words[_child_id], already_set)
            events = events + _event

        if root.rel in Subjects:
            _head = self.words[root.head]
            while _head.rel not in Clauses and _head.rel not in clause_complement \
                    and _head.rel != 'root' and _head.postag not in ['VERB', 'ADJ']:  # 主谓短语、动作从句
                _head = self.words[_head.head]
            already_set.add(_head.id)
            event = HpSent(_head.id, root, _head, _head.head)
            events.append(event)
            removeParent(_head)

        if root.rel in Objects:

            def get_subject(verb_word):
                for word in self.words:
                    if word.rel in Subjects and word.head == verb_word.id:
                        return word
                return None

            _head = self.words[root.head]

            while _head.rel not in Clauses and _head.rel not in clause_complement \
                    and _head.rel != 'root' and _head.postag not in ['VERB']:  # 动宾短语、动作从句
                _head = self.words[_head.head]

            # 如果从句有2个及以上主语or宾语，认定最开始的为控制范围最广的主语，其他主语不可被继承到节点句子。
            subject = get_subject(_head)
            already_set.add(_head.id)
            event = HpSent(_head.id, subject, _head, _head.head, root)  # 增加object
            events.append(event)
            removeParent(_head)

        elif root.rel in Clauses and root.id not in already_set:  # 子树不含主谓宾，但本身有动作含义,此时补语从句不单独化为事件。
            if root.postag in ['VERB', 'ADJ']:  # 形容词做宾语？
                already_set.add(root.id)
                subject = None
                events.append(HpSent(root.id, subject, root, root.head))
                removeParent(root)
            elif root.id > 0:
                # 若前面词已经被拆分为短句，则后面的并列关系应该单独成短句，不能直接合并到父节点所在树。
                pre_word = self.words[root.id - 1]

                def find_ancestor(_w):
                    ancestor = _w
                    while ancestor.head != -1:
                        ancestor = self.words[ancestor.head]
                    return ancestor

                root_ancestor = find_ancestor(root)
                pre_ancestor = find_ancestor(pre_word)
                if root_ancestor.id != pre_ancestor.id:  # 不在一棵树上
                    already_set.add(root.id)
                    subject = None
                    events.append(HpSent(root.id, subject, root, root.head))
                    removeParent(root)

        elif root.rel == 'root' and root.id not in already_set:  # 保证event一定不为空
            already_set.add(root.id)
            subject = None
            events.append(HpSent(root.id, subject, root, root.head))
            removeParent(root)

        return events, already_set

    def __splitEvents(self, events: list):
        """
        span split 将事件划分为连续字符段
        :param events:
        :return:
        """
        result = []
        for event in events:
            # subject
            if event.subject:
                subs = []
                for sub_word in event.subject:
                    subs.append(self._tree_span(sub_word))
                    if sub_word.head != -1:  # 去除主语
                        self.words[sub_word.head].child.remove(sub_word.id)
                        self.words[sub_word.id].head = -1
                event.subject = subs
            # object
            if event.object:
                objs = []
                for obj_word in event.object:
                    objs.append(self._tree_span(obj_word))
                    # 去除object的所有孩子节点，因为其text已经记录
                    child_list = obj_word.child.copy()
                    for child in child_list:
                        self.words[child].head = -1
                        self.words[obj_word.id].child.remove(child)

                event.object = objs
            result.append(event)
        return result
# '''
#     def __LogoEntitySubevent(self, events: list):
#         """
#         根据关键词标注events中的实体：
#             Subject：device、human、victim
#             Event：deviation、safeguard、consequence、ordinary
#         Entity: [id, type, xspan, text]
#         :param events:
#         :return:
#         """
#         entities = []
#         subEvents = []
#         sub_set = []
#         isDevia = False  # only one deviation in hazard
#         isCons = False  # only one consequence in hazard
#         for event in events:
#             # deviation, consequence, safeguard, ordinary
#             # 主谓宾含有关键词
#             p = self._tree_span(event.predicate).text
#             if not isDevia and self._span_element(p, self.devi_key):
#                 p_entity_type = "Deviation"
#                 # isDevia = True
#             elif not isCons and self._span_element(p, self.cons_key):
#                 p_entity_type = "Consequence"
#                 # isCons = True
#             elif self._span_element(p, self.safe_key):
#                 p_entity_type = "Safeguard"
#             else:
#                 p_entity_type = "Ordinary"
#
#             # get subject
#             def get_subject(_e):
#                 if _e.subject:
#                     return _e.subject[-1]
#                 else:
#                     while _e.head >= 0 and not events[_e.head].subject:
#                         _e = events[_e.head]
#                     if _e.head == -1:
#                         return None
#                     else:
#                         return events[_e.head].subject[0]
#
#             sub = get_subject(event)
#             if sub is not None:
#                 subEvents.append(['R{0}'.format(len(subEvents)), 'Subject', (sub.id, event.predicate.id)])
#             if p_entity_type == "Consequence":
#                 # 先判断宾语是否存在,取最近的宾语；是否为被动句，若不是则取最近的主语，否则取宾语。
#                 if event.object:
#                     core_obj = event.object[0]
#                     text_obj = self._tree_span(core_obj)
#                     if core_obj.head != -1:
#                         self.words[core_obj.head].child.remove(core_obj.id)
#                         self.words[core_obj.id].head = -1
#
#                     entities.append([core_obj.id, 'Victim', text_obj.span, text_obj.text])
#                     sub_set.append(core_obj.id)
#                 elif not self.isPass(event.predicate) and sub is not None:
#                     print('no pass...')
#                     if sub.id not in sub_set:
#                         text_sub = self._tree_span(sub)
#                         if sub.head != -1:
#                             self.words[sub.head].child.remove(sub.id)
#                             self.words[sub.id].head = -1
#
#                         entities.append([sub.id, 'Victim', text_sub.span, text_sub.text])
#                         sub_set.append(sub.id)
#                     else:
#                         # 更改已有entity
#                         for i, e in enumerate(entities):
#                             if e[0] == sub.id:
#                                 entities[i][1] = 'Victim'
#             # subject
#             for word in event.subject:
#                 if word.id not in sub_set:
#                     text_word = self._tree_span(word)
#                     person_regex = '.*人员|.*人|.+工'
#                     person = re.search(person_regex, text_word.text)
#                     if person is None:
#                         entity_type = 'Environment'
#                     else:
#                         entity_type = 'Human'
#                     if word.head != -1:
#                         self.words[word.head].child.remove(word.id)
#                         self.words[word.id].head = -1
#
#                     entities.append([word.id, entity_type, text_word.span, text_word.text])
#                     sub_set.append(word.id)
#             text_predicate = self._tree_span(event.predicate)
#             entities.append([event.predicate.id, p_entity_type, text_predicate.span, text_predicate.text])
#
#         entities = sorted(entities, key=lambda x: x[2][0])
#         for i, entity in enumerate(entities):
#             id = entity[0]
#             entities[i][0] = 'T{0}'.format(i)
#             # log subject relations
#             for j, rel in enumerate(subEvents):
#                 if entity[1] in ['Environment', 'Human', 'Victim'] and str(rel[2][0]) == str(id):
#                     subEvents[j][2] = ('T{0}'.format(i), rel[2][1])
#                 elif entity[1] in ['Deviation', 'Safeguard', 'Consequence', 'Ordinary'] and str(rel[2][1]) == str(id):
#                     subEvents[j][2] = (rel[2][0], 'T{0}'.format(i))
#
#         return entities, subEvents
# '''

    def __LogoRelation(self, result):
        """
        根据关联词匹配标注events之间因果关系：
            seq、but、cause、condition
            顺承、 转折、 因果、  条件
        :param result:
        :return:
        """
        relations = []
        patternExtract = PatternExtraction()
        rels = patternExtract.add_relation(self.sent)
        for r in rels:  # 查找关联词对应的deviation, consequence, safeguard, ordinary
            pre = None
            pos = None
            for i, entity in enumerate(result.entities):
                if entity[2][0] <= r[1] < entity[2][1]:
                    pre = i
                    while pre < len(result.entities) and result.entities[pre][1] in ['Environment', 'Human', 'Victim']:
                        pre = pre + 1
                    if pre >= len(result.entities):  # 极端情况
                        pre = None
                elif entity[2][0] <= r[2] < entity[2][1]:
                    pos = i
                    while pos < len(result.entities) and result.entities[pos][1] in ['Environment', 'Human', 'Victim']:
                        pos = pos + 1
                    if pos >= len(result.entities):
                        pos = None
                if pre is not None and pos is not None and pre != pos:
                    relations.append(
                        ['R{0}'.format(len(relations)), r[0], (result.entities[pre][0], result.entities[pos][0])])
                    break
        # Deviation和Consequence之间存在Cause
        deviation = None
        consequence = None
        for i, entity in enumerate(result.entities):
            if deviation is None and entity[1] == 'Deviation':
                deviation = entity
            if consequence is None and entity[1] == 'Consequence':
                consequence = entity
            if deviation is not None and consequence is not None:
                relations.append(['R{0}'.format(len(relations)), 'Cause', (deviation[0], consequence[0])])
                break
        return relations

    def _span_keyword(self, _w, _text):
        flag = False
        if _w.text == _text and _w.postag == 'ADP' and _w.rel == 'case':
            return True
        for child_id in _w.child:
            flag |= self._span_keyword(self.words[child_id], _text)
        return flag

    # 被动语态
    def isPass(self, _w):
        if _w.rel == 'aux:pass':
            return True
        flag = False
        for _child_id in _w.child:
            flag |= self.isPass(self.words[_child_id])
        return flag

    def _span_element(self, text, key_list):  # 合成为句子，后匹配
        for i in key_list:
            if i in text:
                return True
        return False

    def _tree_span(self, _w):
        def _span(_w):
            text_set = [_w]
            for _child_id in _w.child:
                text_set.extend(_span(self.words[_child_id]))
            return sorted(text_set, key=lambda x: x.id)

        # 只提取中心词周围连续的文本
        text_list = _span(_w)
        w_0 = text_list[0]
        new_list = [HpWord(w_0.id, w_0.text, w_0.rel, w_0.postag, w_0.head, w_0.span)]
        for item in text_list[1:]:
            if item.span[0] == new_list[-1].span[1]:  # 连续的
                new_list[-1].text = new_list[-1].text + item.text
                new_list[-1].span = (new_list[-1].span[0], item.span[1])
            elif item.span[0] > new_list[-1].span[1]:  # 不连续
                new_list.append(HpWord(item.id, item.text, item.rel, item.postag, item.head, item.span))
            else:
                print('语法分析错误！')
        for item in new_list:
            if _w.span[0] >= item.span[0] and _w.span[1] <= item.span[1]:
                return item
        return _w

    def split_sents(self, content):
        return [re.sub(' +', '，', sentence) for sentence in re.split(r'[？?！!。；;：:\n\r]', content) if sentence]

    # 对句子进行关联词匹配，添加','
    def sent_pre_process(self, content):
        event_extraction = PatternExtraction()
        sents = self.split_sents(content)
        content = ''
        for s in sents:
            content += event_extraction.add_comma(s) + '。'
        return content


def main():
    parser = Trankit2Parser()
    s = '配电箱无防护门。配电箱内的电线风吹雨淋后老化漏电。电工在进行作业时，未穿戴绝缘手套、绝缘鞋。造成人员触电。虽发现及时就医治疗，但抢救无效死亡。'
    s = "高速轴联轴器、低速轴联轴器、制动轮、制动盘及液力偶合器都应加装防护罩。当驱动装置设置在地面或人员能接近的平台上且带速大于3.15m/s时，整个驱动装置范围应采用高度不低于1500mm的护栏予以防护。"

    print('处理前:' + s)
    s = parser.sent_pre_process(s)
    '''
    对隐患描述进行文法分析，得到事件关联
    '''
    parser.setSent(s)
    result = parser.parser()
    result.outFile('../data/output/trankit', 'test')
    j = result.outJson()
    print(j)


if __name__ == '__main__':
    main()
