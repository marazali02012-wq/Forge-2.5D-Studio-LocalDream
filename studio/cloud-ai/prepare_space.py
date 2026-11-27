"""Create only the files needed by a dedicated Hugging Face Docker Space."""
from pathlib import Path
import shutil
import sys
root=Path(__file__).resolve().parent
out=Path(sys.argv[1])
out.mkdir(parents=True,exist_ok=True)
for name in ('README.md','Dockerfile','OCI.md'):
    shutil.copy2(root/'space'/name,out/name)
for name in ('cpu_probe.py','private_api.py','rig_adaptive.py','texture_atlas.py'):
    shutil.copy2(root/name,out/name)
shutil.copy2(root.parent/'torchmcubes.py',out/'torchmcubes.py')
