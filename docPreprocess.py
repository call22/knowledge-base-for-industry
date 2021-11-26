import os.path
from tqdm import tqdm
import docx
import pandas as pd
import json
import re
from elementExtract.ruleExt1 import RuleExtract1


def preprocess(doc_path, out_path):
    """
    对清单文件预处理为json规则列表形式
    :param out_path:
    :param doc_path: 文件路径
    :return: None
    """
    text = []
    import os
    for filename in os.listdir(doc_path):
        filepath = os.path.join(doc_path, filename)
        if filename[-5:] == '.docx':
            f = docx.Document(filepath)
            for paragraph in f.paragraphs:
                sentences = paragraph.text.replace(' ', '').split('\n')
                text.extend(sentences)

            for table in f.tables:
                for row in table.rows:
                    rule = ''
                    for cell in row.cells:
                        rule += cell.text + ' | '
                    text.append(rule.replace(' ', '').strip('|'))
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f.readlines():
                    text.append(line.replace(' ', '').strip('\n'))

    with open(out_path, 'w', encoding='utf-8') as f:
        for item in text:
            f.write(item)
            if len(item) >= 1 and item[-1] in '；。？！：':
                f.write('\n')


def table2json(input_path):
    """
    提取文件中的表格，每行转为一个item，包含多个属性，不分层级
    :param input_path: 文件路径
    :return: json文件
    """
    dicts = []
    if input_path[-5:] == '.docx':
        f = docx.Document(input_path)
        for table in f.tables:
            attributes = [x.text.replace('\n', '').replace(' ', '') for x in table.rows[0].cells]
            add_attr = []
            for row in tqdm(table.rows[1:]):
                text_set = list(set([x.text for x in row.cells]))
                if len(text_set) == 2:
                    _ = row.cells[0].text.replace('\n', '').replace(' ', '')
                    if ('（' in _ or '(' in _) and len(add_attr) == 2:
                        add_attr.pop()
                    if _ in ['一', '二', '三', '四', '五', '六', '七', '八', '九', '零', '〇']:
                        add_attr = []
                    add_attr.append(_ + ' ' + row.cells[1].text.replace(' ', '').replace('\n', ''))
                else:
                    item = {'类型': add_attr}
                    for idx, att in enumerate(attributes):
                        item[str(att)] = row.cells[idx].text
                        # 日期统一用 Y-m-d形式记录
                        if '日期' in att:
                            item[str(att)] = item[str(att)].replace('/', '-')
                    dicts.append(item)
    elif input_path[-5:] == '.xlsx':
        df = pd.read_excel(input_path, header=1)
        attributes = [x.replace('\n', '').replace(' ', '') for x in df.columns]
        add_attr = []
        for index, row in df.iterrows():
            if pd.isna(row[4]):  # 标准编号不能为空
                _ = row[0].replace('\n', '').replace(' ', '')
                if ('（' in _ or '(' in _) and len(add_attr) == 2:
                    add_attr.pop()
                if _ in ['一', '二', '三', '四', '五', '六', '七', '八', '九', '零', '〇']:
                    add_attr = []
                add_attr.append(_ + ' ' + row[1].replace(' ', '').replace('\n', ''))
            else:
                item = {'类型': add_attr}
                for attr in attributes:
                    item[str(attr)] = str(row[str(attr)])
                    if '日期' in str(attr):
                        item[str(attr)] = item[str(attr)].split()[0]
                dicts.append(item)

    out_path = os.path.splitext(input_path)[0] + '.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(dicts, f, ensure_ascii=False, indent=2)


def clearJson(input_path):
    """
    对json文件数据清洗，去除多余换行符，序号补全，统一标准编号，去除编号空格
    :param input_path:
    :return:
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for i, item in enumerate(data):
        keys = list(item.keys())
        for key in keys:
            if key == '序号':
                item['序号'] = str(i + 1)
            elif key == '相关条款说明' or key == '最新实施/新修法律法规解读' or key == '检查内容':
                reg = r'\n+'
                item[key] = re.sub(reg, '\n', item[key])
            elif key == '标准编号' or key == '文件编号':
                item[key] = item[key].replace('\n', '').replace(' ', '')
                item['标准编号'] = item[key]  # 统一添加标准编号
            elif key != '类型':
                item[key] = item[key].replace('\n', '')
        if item.get('文件编号', True) is not True:
            del item['文件编号']
        data[i] = item
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def formData(input_path):
    """
    data.json文件提出“标准编号”属性（去除空格），可能有多个编号，故按list存储
    :param input_path:
    :return:
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for i, item in enumerate(data):
        item['检查依据'] = item['检查依据'].replace(' ', '')
        reg = '》([^条]*)第+'
        item['标准编号'] = list(set(re.findall(reg, item['检查依据'])))
        data[i] = item
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extractRuleData(input_path, output_path):
    """
    对data.json文件中的“检查内容”进行解析，得到展示形式和应用形式的规则
    :param input_path:
    :param output_path:
    :return:
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    ruleExtr1 = RuleExtract1()
    for item in tqdm(data):
        ruleExtr1.setSent(item['检查内容'])
        ruleExtr1.parser()
        item['viewForm'] = ruleExtr1.genViewVer()
        item['appForm'] = ruleExtr1.genAppVer()
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 解析rule.json中viewForm和appForm属性
def analysisRule(input_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for item in data:
        viewForm = item['viewForm'][0]
        for key in viewForm.keys():
            print(key)
            _key = viewForm[key]


# TODO: 将2020和2021文件合并
def jsonMerge(out_path, **input_path):
    pass


if __name__ == '__main__':
    # path = 'data/doc'
    # rule_path = 'data/rule.txt'
    # preprocess(path, rule_path)
    # table2json('data/law/安全生产法律法规列表.xlsx')
    # table2json('data/law/2020最新安全生产法律法规清单.docx')
    # table2json('data/law/安全法规列表-2.docx')
    # clearJson('data/law/安全生产法律法规列表.json')
    # clearJson('data/law/安全法规列表-2.json')
    # clearJson('data/law/2020最新安全生产法律法规清单.json')
    # clearJson('data/data.json')
    # formData('data/data.json')
    # extractRuleData('data/data.json', 'data/rule.json')
    pass
