
class HpWord:
    def __init__(self, wid, text, rel, postag, head, span=(0, 0)):
        self.id = wid
        self.text = text
        self.rel = rel
        self.postag = postag
        self.head = head
        self.span = span
        self.tag = []   # 标记
        self.child = []

    def __repr__(self):
        return f'<id::{self.id}, text::{self.text}, tag::{self.tag}, rel::{self.rel}, postag::{self.postag}, head::{self.head}, span::{self.span}, child::{self.child}> '
        # return f'<id::{self.id}, text::{self.text}, tag::{self.tag}, head::{self.head}> '
