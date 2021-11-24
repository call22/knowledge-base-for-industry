from tqdm import tqdm
import json
from ruleExtraction import RuleExtract


def extract_rule(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data_list = json.load(f)
    ruleExtract = RuleExtract('')
    for i, item in tqdm(enumerate(data_list)):
        checkContent = item['检查内容']
        # TODO: 抽取检查规则
        ruleExtract.set_text(checkContent)
        if item['序号'] == '48':
            print('hhh')
        rules = ruleExtract.extract()
        if len(rules) > 0:
            print(item['序号'])
        data_list[i]['关联关系'] = rules
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data_list, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    data_path = 'data/data.json'
    rules_path = 'data/rule.json'
    extract_rule(data_path, rules_path)
