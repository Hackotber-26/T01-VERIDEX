"""Create a portable synthetic smoke dataset and Gemma 4 QLoRA notebook."""
import ast
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'training' / 'gemma4-finetune'

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    base = dict(same_scene='yes', original_defect_visible='yes', target_visible_after='yes', obstruction='no', appearance='repair_visible')
    targets = [
        ('repaired', 'after.png', dict(base, evidence='The original pothole is visible in BEFORE. The same area appears patched with asphalt in AFTER.')),
        ('unchanged', 'before.png', dict(base, appearance='defect_visible', evidence='The same pothole remains visible in the identical completion image.')),
        ('obstructed', 'after-blocked.png', dict(base, target_visible_after='no', obstruction='yes', appearance='uncertain', evidence='Cardboard covers the original target area in AFTER, preventing visual assessment.')),
    ]
    rows = [dict(id=name, split='train', synthetic=True, location_group='generated-scene-001',
                 before='images/before.png', after='images/'+after, roi=[.24,.36,.80,.78],
                 observation=target, label_source='Manually authored synthetic teaching target; not independent field ground truth')
            for name, after, target in targets]
    prompt = (ROOT / 'veridex' / 'gemma.py').read_text()
    tree = ast.parse(prompt)
    instruction = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id=='PROMPT' for t in node.targets))
    with zipfile.ZipFile(OUT/'veridex-training.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('train.jsonl', ''.join(json.dumps(r)+'\n' for r in rows))
        z.writestr('instruction.txt', instruction)
        z.writestr('DATA_CARD.txt', 'THREE SYNTHETIC TRAINING EXAMPLES FROM ONE GENERATED SITE. Smoke test only. No validation/test split or real-world accuracy claim. Training this tiny set may overfit or degrade the model. No real repair dataset is included.\n')
        for name in ['before.png','after.png','after-blocked.png']:
            z.write(ROOT/'examples/synthetic-pair-001'/name, 'images/'+name)

    cells = []
    def md(s): cells.append({'cell_type':'markdown','metadata':{},'source':s.splitlines(True)})
    def code(s): cells.append({'cell_type':'code','metadata':{},'source':s.splitlines(True),'execution_count':None,'outputs':[]})
    md('''# VERIDEX: Gemma 4 vision QLoRA

This notebook changes model weights through LoRA adapters. It is **prepared, not executed**.
Start with Runtime > Change runtime type > T4 GPU. Free GPU access is subject to Colab availability and quotas.

The starter ZIP has **3 synthetic examples from one site**. Its purpose is to verify the training/save loop, not produce a reliable model. There is no independent evaluation set. Do not describe training loss or memorized examples as field accuracy.

This uses **Gemma 4 E4B**, a smaller member of the Gemma 4 family, rather than the hosted 26B-A4B model. The adapter applies only to its exact base model. It cannot be attached to the existing Google API endpoint.

Based on the supported [Unsloth Gemma 4 vision notebook](https://github.com/unslothai/notebooks/blob/main/nb/Gemma4_(E4B)-Vision.ipynb) and [training guide](https://unsloth.ai/docs/models/gemma-4/train).
''')
    code('''# Install in a fresh Colab runtime; versions follow the upstream notebook checked 2026-10-31.
%pip install sentencepiece protobuf "datasets==4.3.0" "huggingface_hub>=1.5.0,<2.0" hf_transfer
%pip install --no-deps unsloth_zoo bitsandbytes accelerate peft trl triton unsloth
!unsloth install-kernels
%pip install --no-deps --upgrade "torchao>=0.16.0" timm
%pip install --no-deps transformers==5.5.0 "tokenizers>=0.22.0,<=0.23.0"
import importlib.metadata as metadata
torch_version = tuple(int(x) for x in metadata.version('torch').split('+')[0].split('.')[:2])
codec = {(2,11):'torchcodec>=0.11.0',(2,10):'torchcodec==0.10.*',(2,9):'torchcodec==0.9.*',(2,8):'torchcodec==0.7.*',(2,7):'torchcodec==0.5.*'}.get(torch_version,'torchcodec')
%pip install $codec
''')
    code('''from unsloth import FastVisionModel, get_chat_template
import torch
assert torch.cuda.is_available(), 'Select a GPU runtime, then rerun.'
print(torch.cuda.get_device_name(0))
print('VRAM GB:', round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1))
''')
    md('## Upload the starter bundle\nUpload `veridex-training.zip` from the folder beside this notebook. It contains only synthetic images and teaching labels, not your API key. A Gemini API key is not required for local-weight training. Model access may separately require a Hugging Face login; enter credentials privately only if the model repository requests them.')
    code('''from google.colab import files
from pathlib import Path
import zipfile, json
uploaded = files.upload()
assert 'veridex-training.zip' in uploaded, 'Upload veridex-training.zip'
data_root = Path('/content/veridex-data')
data_root.mkdir(exist_ok=True)
with zipfile.ZipFile('veridex-training.zip') as archive:
    assert sum(item.file_size for item in archive.infolist()) < 100_000_000, 'Unexpected bundle size'
    for item in archive.infolist():
        assert (data_root/item.filename).resolve().is_relative_to(data_root.resolve()), 'Unsafe ZIP path'
    archive.extractall(data_root)
rows = [json.loads(line) for line in (data_root/'train.jsonl').read_text().splitlines() if line.strip()]
assert rows and all(row['split']=='train' for row in rows)
print((data_root/'DATA_CARD.txt').read_text())
''')
    code('''from PIL import Image, ImageOps
instruction = (data_root/'instruction.txt').read_text()
def conversation(row):
    def image(name):
        with Image.open(data_root/name) as original:
            result = ImageOps.exif_transpose(original).convert('RGB')
        result.thumbnail((512,512))
        return result
    before, after = image(row['before']), image(row['after'])
    x1,y1,x2,y2 = row['roi']
    crop = before.crop((int(x1*before.width),int(y1*before.height),int(x2*before.width),int(y2*before.height)))
    return {'messages':[
        {'role':'user','content':[
            {'type':'text','text':instruction},
            {'type':'text','text':'BEFORE full image'}, {'type':'image','image':before},
            {'type':'text','text':'BEFORE target crop'}, {'type':'image','image':crop},
            {'type':'text','text':'Claimed AFTER full image'}, {'type':'image','image':after}]},
        {'role':'assistant','content':[{'type':'text','text':json.dumps(row['observation'])}]}]}
train_data = [conversation(row) for row in rows]
print('Training examples:',len(train_data))
''')
    code('''BASE_MODEL = 'unsloth/gemma-4-E4B-it'
model, processor = FastVisionModel.from_pretrained(
    BASE_MODEL, load_in_4bit=True, use_gradient_checkpointing='unsloth')
model = FastVisionModel.get_peft_model(
    model, finetune_vision_layers=False, finetune_language_layers=True,
    finetune_attention_modules=True, finetune_mlp_modules=False,
    r=8, lora_alpha=8, lora_dropout=0, bias='none', random_state=3407)
processor = get_chat_template(processor, 'gemma-4')
model.print_trainable_parameters()
''')
    md('## Adapter training\nThis smoke run performs 10 optimizer steps. The vision encoder stays frozen; language attention adapters learn the structured response task conditioned on images. More steps on these same three examples will not establish generalization. Save this smoke adapter separately from any future production model.')
    code('''from unsloth.trainer import UnslothVisionDataCollator
from trl import SFTTrainer, SFTConfig
FastVisionModel.for_training(model)
trainer = SFTTrainer(
    model=model, train_dataset=train_data, processing_class=processor.tokenizer,
    data_collator=UnslothVisionDataCollator(model,processor),
    args=SFTConfig(
        per_device_train_batch_size=1, gradient_accumulation_steps=1,
        max_steps=10, learning_rate=5e-5, max_grad_norm=0.3,
        logging_steps=1, save_strategy='no', optim='adamw_8bit',
        weight_decay=0.001, seed=3407, output_dir='/content/veridex-smoke',
        report_to='none', remove_unused_columns=False, dataset_text_field='',
        dataset_kwargs={'skip_prepare_dataset':True}, max_length=4096))
stats = trainer.train()
print(stats.metrics)
assert stats.global_step > 0, 'Training did not complete any steps'
''')
    code('''import shutil
output = Path('/content/veridex-gemma4-e4b-smoke-adapter')
model.save_pretrained(str(output))
processor.save_pretrained(str(output))
(output/'VERIDEX_MODEL_CARD.json').write_text(json.dumps({
    'base_model':BASE_MODEL,'training_examples':len(train_data),
    'training_steps':stats.global_step,'synthetic':True,'independent_test_accuracy':None,
    'scope':'Training smoke adapter only. Not validated for real repair review.',
    'metrics':stats.metrics},indent=2))
(output/'training-log.json').write_text(json.dumps(trainer.state.log_history,indent=2))
assert list(output.glob('adapter_model.*')), 'No saved adapter weights found'
archive = shutil.make_archive('/content/veridex-gemma4-smoke-adapter','zip',output)
files.download(archive)
''')
    md('''## Before calling this a useful fine-tuned model

Add permissioned real repair pairs with independently adjudicated observations. Keep each location and every derivative in one split. Train on training locations, select settings on validation locations and compare the **same E4B base** with its adapter on untouched test locations. Include wrong-scene, obstruction, lighting and nearby-patch cases. Record provider/training failures. Do not compare this E4B adapter to 26B-A4B and attribute differences only to tuning.

The existing `python -m veridex` command still uses the hosted base model. The downloaded adapter requires a separate base+adapter inference deployment; it does not modify Google's hosted endpoint.
''')
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'colab':{'name':'VERIDEX_Gemma4_Finetune.ipynb'},'accelerator':'GPU','kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells}
    path=OUT/'VERIDEX_Gemma4_Finetune.ipynb'
    path.write_text(json.dumps(notebook,indent=2))
    # Static syntax check; IPython shell/magic cells require the GPU runtime to execute.
    for cell in cells:
        if cell['cell_type']=='code':
            source=''.join(cell['source'])
            ast.parse('\n'.join(line for line in source.splitlines() if not line.startswith(('%','!'))))
    print(path)
    print(OUT/'veridex-training.zip')

if __name__=='__main__': build()
