import torch,numpy as np
from skimage.measure import marching_cubes as mc
def marching_cubes(volume,level):
    v,f,_,_=mc(volume.detach().cpu().numpy(),level=level,gradient_direction='ascent',allow_degenerate=False)
    return torch.from_numpy(v[:,::-1].copy()).float(),torch.from_numpy(f.copy().astype(np.int64))
