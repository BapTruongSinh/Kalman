"""Fix the KeyError 'SIM' bug in ARX_Model_Validation.ipynb"""
import json

path = r'c:\Users\minht\OneDrive\Desktop\ARX-Model\ARX_Model_Validation.ipynb'

with open(path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if 'Bar chart: FIT scores across seeds' in src:
            new_source = []
            for line in cell['source']:
                if "metric.split('_', 1)[1].upper()" in line:
                    new_source.append("    metrics_key = {'FIT_1step': 'metrics_1step', 'FIT_12step': 'metrics_n_step', 'FIT_sim': 'metrics_sim'}[metric]\n")
                    new_source.append("    orig_val = saved_model['slices']['test'][metrics_key]['FIT']\n")
                else:
                    new_source.append(line)
            cell['source'] = new_source
            cell['outputs'] = []
            cell['execution_count'] = None
            print('Fixed bar chart cell!')
            break

with open(path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Saved successfully.')
