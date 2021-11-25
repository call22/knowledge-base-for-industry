from trankit import Pipeline
# from patternExtraction import PatternExtraction
import re

# TODO: 检查内容中”实体“、”动作“、”否定词：应，禁止“抽取


def split_sents(content):
    return [re.sub(' +', '，', sentence) for sentence in re.split(r'[？?！!。；;：:\n\r]', content) if sentence]


class RuleExtract:
    def __init__(self, text):
        self.text = text

    def set_text(self, text):
        self.text = text

    def extract(self):
        """
        按照一定规则抽取句子中的规则，默认为语法规则
        :param extract_type: 语法规则、语义规则等
        :return: 规则列表
        """
        rules = []
        must_wds = ['应该', '必须', '应']
        ban_wds = ['不应', '严禁', '禁止', '不得', '不能']
        if_wds = [[['如果'], ['则']],
                  [['当.+时'], ['必须', '应该', '应', '']]]

        p = Pipeline('chinese')
        analysis = p.posdep(self.text)
        for sentence in analysis.sentences:
            rules.extend(self._syntaxlevel_extract(sentence.tokens))
        return rules

    def _syntaxlevel_extract(self, sentence):
        """
        遍历语法树，从句子的语法结构中提取规则
        :param sentence: 句子的语法结构，dict形式{'id', 'text',''upos', 'xpos', 'feats', 'head', 'deprel', 'dspan', 'span'}
        :return: 规则list
        """

        return []
