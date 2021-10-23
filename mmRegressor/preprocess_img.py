import numpy as np 
from scipy.io import loadmat,savemat
from PIL import Image
import torch

#calculating least sqaures problem
def POS(xp,x):
    npts = xp.shape[1]

    A = np.zeros([2*npts,8])

    A[0:2*npts-1:2,0:3] = x.transpose()
    A[0:2*npts-1:2,3] = 1

    A[1:2*npts:2,4:7] = x.transpose()
    A[1:2*npts:2,7] = 1

    b = np.reshape(xp.transpose(),[2*npts,1])

    k,_,_,_ = np.linalg.lstsq(A,b, rcond=None)

    R1 = k[0:3]
    R2 = k[4:7]
    sTx = k[3]
    sTy = k[7]
    s = (np.linalg.norm(R1) + np.linalg.norm(R2))/2
    t = np.stack([sTx,sTy],axis = 0)

    return t,s

# It first uses this to roughly unify the shape, but actually put it in the center!!!
def process_img(img,lm,t,s,render_size=224, mask=None):
    w0,h0 = img.size
    
    # This can change the size of the picture and put the face in the approximate center
    img = img.transform(img.size, Image.AFFINE, (1, 0, t[0] - w0/2, 0, 1, h0/2 - t[1]))
    if mask is not None:
        mask = mask.transform(mask.size, Image.AFFINE, (1, 0, t[0]-w0/2, 0, 1, h0/2 - t[1]))
    
    w = (w0/s*102).astype(np.int32)
    h = (h0/s*102).astype(np.int32)
    
    # crop the image to 224*224 from image center
    left = (w/2 - 112).astype(np.int32) 
    right = left + 224
    up = (h/2 - 112).astype(np.int32)
    below = up + 224

    left_c = round(w0/w * left)
    right_c = round(w0/w * right)
    up_c = round(h0/h * up)
    below_c = round(h0/h * below)
    cropped_img = img.crop((left_c,up_c,right_c,below_c)).resize((render_size, render_size), resample=Image.BILINEAR)
    # cropped_img = np.array(cropped_img)[:,:,::-1]
    # cropped_img = np.expand_dims(cropped_img, 0)
    
    img = img.resize((w,h),resample = Image.BILINEAR)
    if mask is not None:
        mask = mask.resize((w,h), resample = Image.BILINEAR)
    lm = np.stack([lm[:,0] - t[0] + w0/2,lm[:,1] - t[1] + h0/2],axis = 1)/s*102 

    img = img.crop((left,up,right,below))
    if mask is not None:
        mask = mask.crop((left,up,right,below))
    img = np.array(img)
    img = img[:,:,::-1] # Became BGR
    img = np.expand_dims(img,0)
    if mask is not None:
        mask = np.expand_dims(mask,0)
    lm = lm - np.reshape(np.array([(w/2 - 112),(h/2-112)]),[1,2])

    return img, lm, mask, cropped_img, [left_c, right_c, up_c, below_c]

def _process_img(img,lm,t,s,render_size=224):
    w0,h0 = img.size
    
    # This can change the size of the picture and put the face in the approximate center
    img = img.transform(img.size, Image.AFFINE, (1, 0, t[0] - w0/2, 0, 1, h0/2 - t[1]))
    
    w = (w0/s*102).astype(np.int32)
    h = (h0/s*102).astype(np.int32)
    
    # crop the image to 224*224 from image center
    left = (w/2 - 112).astype(np.int32) 
    right = left + 224
    up = (h/2 - 112).astype(np.int32)
    below = up + 224

    left_c = round(w0/w * left)
    right_c = round(w0/w * right)
    up_c = round(h0/h * up)
    below_c = round(h0/h * below)
    if render_size is None:
        _w = right_c - left_c
        _h = below_c - up_c
        if _w < _h:
            gap = (_h-_w)//2
            left_c -= gap
            right_c += gap
            render_size = _w
        elif _w > _h:
            gap = (_w-_h)//2
            up_c -= gap
            below_c += gap
            render_size = _h
        else:
            render_size = _h

    # cropped_img = img.crop((left_c,up_c,right_c,below_c)).resize((render_size, render_size), resample=Image.BILINEAR)
    # cropped_img = np.array(cropped_img)[:,:,::-1]
    # cropped_img = np.expand_dims(cropped_img, 0)
    
    img = img.resize((w,h),resample = Image.BILINEAR)
    lm = np.stack([lm[:,0] - t[0] + w0/2,lm[:,1] - t[1] + h0/2],axis = 1)/s*102 

    img = img.crop((left,up,right,below))
    img = np.array(img)
    # img = img[:,:,::-1] # Became BGR
    #img = np.expand_dims(img,0)
    lm = lm - np.reshape(np.array([(w/2 - 112),(h/2-112)]),[1,2])

    return img, lm, img, [left_c, right_c, up_c, below_c, render_size, t[0] - w0/2, h0/2 - t[1]]


# resize and crop input images before sending to the R-Net
def Preprocess(img, lm, lm3D, render_size=224, box=False):
    w0,h0 = img.size

    # change from image plane coordinates to 3D sapce coordinates(X-Y plane)
    lm = np.stack([lm[:,0],h0 - 1 - lm[:,1]], axis = 1)

    # calculate translation and scale factors using 5 facial landmarks and standard landmarks
	# lm3D -> lm
    t,s = POS(lm.transpose(),lm3D.transpose())

    # processing the image
    img_new, lm, cropped_img, crop_box = _process_img(img,lm,t,s,render_size)
    #lm_new = np.stack([lm_new[:,0],223-lm_new[:,1]], axis = 1)
    # trans_params = np.array([w0,h0,102.0/s,t[0][0],t[1][0]])

    if box:
        return img_new, cropped_img, crop_box
    return img_new, cropped_img


def PreprocessNoMask(img, lm, lm3D, render_size=224):
    w0,h0 = img.size

    # change from image plane coordinates to 3D sapce coordinates(X-Y plane)
    lm = np.stack([lm[:,0],h0 - 1 - lm[:,1]], axis = 1)

    # calculate translation and scale factors using 5 facial landmarks and standard landmarks
	# lm3D -> lm
    t,s = POS(lm.transpose(),lm3D.transpose())

    # processing the image
    img_new, _, _, cropped_img, _ = process_img(img,lm,t,s,render_size)
    #lm_new = np.stack([lm_new[:,0],223-lm_new[:,1]], axis = 1)
    # trans_params = np.array([w0,h0,102.0/s,t[0][0],t[1][0]])

    return img_new, cropped_img