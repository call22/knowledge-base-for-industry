import os


class HpWord:
    def __init__(self, wid, text, rel, postag, head, span=(0, 0)):
        self.id = wid
        self.text = text
        self.rel = rel
        self.postag = postag
        self.head = head
        self.span = span
        # self.flag = True
        self.child = []

    def __repr__(self):
        return f'<id::{self.id}, text::{self.text}, rel::{self.rel}, postag::{self.postag}, head::{self.head}, span::{self.span}, child::{self.child}> '


class HpSent:
    def __init__(self, sid: int, subj, pred, head, obj=None):
        self.id = sid
        if subj is None:
            self.subject = []
        else:
            self.subject = [subj]
        if obj is None:
            self.object = []
        else:
            self.object = [obj]
        self.predicate = pred
        self.head = head
        self.span = (0, 0)
        self.relation = []
        self.child = []
        self.elementType = set()

    def __repr__(self):
        return f'<id::{self.id}, subject::{self.subject}, predicate::{self.predicate}, object::{self.object}' \
               f' head::{self.head}, relation::{self.relation}, child::{self.child}, element::{self.elementType}>'


class RelConstruct:
    """
    按照brat需要的格式输入
    brat：https://brat.nlplab.org/
    """
    def __init__(self):
        self.entities = []  # [id, type, xspan, text]
        self.relations = []  # [id, type, (Ti, Tj)]
        self.subEventRels = []  # 主谓关系
        self.sentence = ""

    def geneBrat(self):
        index = len(self.sentence)+2
        ent_len = len(self.entities)
        rel_len = len(self.relations)
        sub_len = len(self.subEventRels)
        entities = self.entities.copy()
        relations = self.relations.copy()
        # 主谓关系对应text句子添加
        for i in range(ent_len):
            entities.append(['T{0}'.format(str(i+ent_len)), self.entities[i][1],
                                  (self.entities[i][2][0]+index, self.entities[i][2][1]+index), self.entities[i][3]])
        for i in range(sub_len):
            pre = int(self.subEventRels[i][2][0].strip('T')) + ent_len
            pos = int(self.subEventRels[i][2][1].strip('T')) + ent_len

            relations.append(['R{0}'.format(str(i+rel_len)), self.subEventRels[i][1],
                                   ('T{0}'.format(pre), 'T{0}'.format(pos))])
        return entities, relations

    # 文件形式
    def outFile(self, com_dir, dir):
        entities, relations = self.geneBrat()
        # 写入
        path = os.path.join(com_dir, dir)
        if not os.path.exists(path):
            os.mkdir(path)
        with open(os.path.join(path, 'text.txt'), 'w', encoding='utf-8') as fin:
            fin.write(self.sentence + '\n')
            fin.write(self.sentence)
        with open(os.path.join(path, 'text.ann'), 'w', encoding='utf-8') as fin:
            for rel in entities:
                fin.write(rel[0]+'\t'+rel[1]+' '+str(rel[2][0]) + ' '+str(rel[2][1])+'\t'+rel[3]+'\n')
            for rel in relations:
                fin.write(rel[0]+'\t'+rel[1]+' Arg1:'+rel[2][0] + ' Arg2:'+rel[2][1]+'\n')

    # json格式
    def outJson(self):
        entities, relations = self.geneBrat()
        docData = {}
        docData["text"] = self.sentence + '\n' + self.sentence
        docData["entities"] = []
        docData["relations"] = []
        for e in entities:
            docData["entities"].append([e[0], e[1], [list(e[2])]])
        for r in relations:
            docData["relations"].append([r[0], r[1], [list(r[2])]])
        return docData

    def grade(self):
        victim = 0
        deviation = 0
        consequence = 0
        others = 0
        for item in self.entities:
            if item[1] == 'Victim':
                victim = 1
            elif item[1] == 'Deviation':
                deviation = 1
            elif item[1] == 'Consequence':
                consequence = 1
            else:
                others = 1
        S_integrity = 3 * (victim + deviation + consequence + others) // 4
        errorCause = False
        for item in self.relations:
            if item[1] in ['Cause','Condition']:
                t1 = self.entities[int(item[2][0].strip('T'))][1]
                t2 = self.entities[int(item[2][1].strip('T'))][1]
                if t1 == 'Consequence' and t2 in ['Ordinary', 'Deviation']:
                    errorCause = True
                    break
        if not errorCause:
            S_integrity += 1
        return S_integrity

