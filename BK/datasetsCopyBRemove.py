# Copyright 2019 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# +==============================================================================

"""Provides data for training and testing."""
import torch
import torchvision
import torchvision.transforms as tvt
import torch.nn as nn
import matplotlib.pyplot as plt
import numpy as np
from torch import optim
import torch.nn.functional as F
import math as m
import time
import os 
#from google.colab import drive
import random
from PIL import Image
from torch.autograd import Variable
from PIL import Image
import numpy
import tensorflow as tf
from pathlib import Path
import pickle
import numpy as np
import torch
import torchvision
import torch.nn.functional as F
import text_model
import test_retrieval
import torch_functions
#import datasets
from tqdm import tqdm as tqdm
import PIL
import argparse
import datasets
import img_text_composition_models
import torchvision.models as models

#Path1=r"D:\personal\master\MyCode\files"
Path1 = r"C:\MMaster\Files"

class BaseDataset(torch.utils.data.Dataset):
  """Base class for a dataset."""

  def __init__(self):
    super(BaseDataset, self).__init__()
    self.imgs = []
    self.test_queries = []

  def get_loader(self,
                 batch_size,
                 shuffle=False,
                 drop_last=False,
                 num_workers=0):
    return torch.utils.data.DataLoader(
        self,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        drop_last=drop_last,
        collate_fn=lambda i: i)

  def get_test_queries(self):
    return self.test_queries

  def get_all_texts(self):
    raise NotImplementedError

  def __getitem__(self, idx):
    return self.generate_random_query_target()

  def generate_random_query_target(self):
    raise NotImplementedError

  def get_img(self, idx, raw_img=False):
    raise NotImplementedError


class CSSDataset(BaseDataset):
  """CSS dataset."""

  def __init__(self, path, split='train', transform=None):
    super(CSSDataset, self).__init__()

    self.img_path = path + '/images/'
    self.transform = transform
    self.split = split
    self.data = np.load(path + '/css_toy_dataset_novel2_small.dup.npy').item()
    self.mods = self.data[self.split]['mods']
    self.imgs = []
    for objects in self.data[self.split]['objects_img']:
      label = len(self.imgs)
      if 'labels' in self.data[self.split]:
        label = self.data[self.split]['labels'][label]
      self.imgs += [{
          'objects': objects,
          'label': label,
          'captions': [str(label)]
      }]

    self.imgid2modtarget = {}
    for i in range(len(self.imgs)):
      self.imgid2modtarget[i] = []
    for i, mod in enumerate(self.mods):
      for k in range(len(mod['from'])):
        f = mod['from'][k]
        t = mod['to'][k]
        self.imgid2modtarget[f] += [(i, t)]

    self.generate_test_queries_()

  def generate_test_queries_(self):
    test_queries = []
    for mod in self.mods:
      for i, j in zip(mod['from'], mod['to']):
        test_queries += [{
            'source_img_id': i,
            'target_caption': self.imgs[j]['captions'][0],
            'mod': {
                'str': mod['to_str']
            }
        }]
    self.test_queries = test_queries

  def get_1st_training_query(self):
    i = np.random.randint(0, len(self.mods))
    mod = self.mods[i]
    j = np.random.randint(0, len(mod['from']))
    self.last_from = mod['from'][j]
    self.last_mod = [i]
    return mod['from'][j], i, mod['to'][j]

  def get_2nd_training_query(self):
    modid, new_to = random.choice(self.imgid2modtarget[self.last_from])
    while modid in self.last_mod:
      modid, new_to = random.choice(self.imgid2modtarget[self.last_from])
    self.last_mod += [modid]
    # mod = self.mods[modid]
    return self.last_from, modid, new_to

  def generate_random_query_target(self):
    try:
      if len(self.last_mod) < 2:
        img1id, modid, img2id = self.get_2nd_training_query()
      else:
        img1id, modid, img2id = self.get_1st_training_query()
    except:
      img1id, modid, img2id = self.get_1st_training_query()

    out = {}
    out['source_img_id'] = img1id
    out['source_img_data'] = self.get_img(img1id)
    out['target_img_id'] = img2id
    out['target_img_data'] = self.get_img(img2id)
    out['mod'] = {'id': modid, 'str': self.mods[modid]['to_str']}
    return out

  def __len__(self):
    return len(self.imgs)

  def get_all_texts(self):
    return [mod['to_str'] for mod in self.mods]

  def get_img(self, idx, raw_img=False, get_2d=False):
    """Gets CSS images."""
    def generate_2d_image(objects):
      img = np.ones((64, 64, 3))
      colortext2values = {
          'gray': [87, 87, 87],
          'red': [244, 35, 35],
          'blue': [42, 75, 215],
          'green': [29, 205, 20],
          'brown': [129, 74, 25],
          'purple': [129, 38, 192],
          'cyan': [41, 208, 208],
          'yellow': [255, 238, 51]
      }
      for obj in objects:
        s = 4.0
        if obj['size'] == 'large':
          s *= 2
        c = [0, 0, 0]
        for j in range(3):
          c[j] = 1.0 * colortext2values[obj['color']][j] / 255.0
        y = obj['pos'][0] * img.shape[0]
        x = obj['pos'][1] * img.shape[1]
        if obj['shape'] == 'rectangle':
          img[int(y - s):int(y + s), int(x - s):int(x + s), :] = c
        if obj['shape'] == 'circle':
          for y0 in range(int(y - s), int(y + s) + 1):
            x0 = x + (abs(y0 - y) - s)
            x1 = 2 * x - x0
            img[y0, int(x0):int(x1), :] = c
        if obj['shape'] == 'triangle':
          for y0 in range(int(y - s), int(y + s)):
            x0 = x + (y0 - y + s) / 2
            x1 = 2 * x - x0
            x0, x1 = min(x0, x1), max(x0, x1)
            img[y0, int(x0):int(x1), :] = c
      return img

    if self.img_path is None or get_2d:
      img = generate_2d_image(self.imgs[idx]['objects'])
    else:
      img_path = self.img_path + ('/css_%s_%06d.png' % (self.split, int(idx)))
      with open(img_path, 'rb') as f:
        img = PIL.Image.open(f)
        img = img.convert('RGB')

    if raw_img:
      return img
    if self.transform:
      img = self.transform(img)
    return img


class Fashion200k1(BaseDataset):
  """Fashion200k dataset."""

  def __init__(self, path, split='train', transform=None):
    super(Fashion200k1, self).__init__()

    self.split = split
    self.transform = transform
    self.img_path = path + '/'

    # get label files for the split
    label_path = path + '/labels/'
    from os import listdir
    from os.path import isfile
    from os.path import join
    label_files = [
        f for f in listdir(label_path) if isfile(join(label_path, f))
    ]
    label_files = [f for f in label_files if split in f]

    # read image info from label files
    self.imgs = []

    def caption_post_process(s):
      return s.strip().replace('.',
                               'dotmark').replace('?', 'questionmark').replace(
                                   '&', 'andmark').replace('*', 'starmark')

    for filename in label_files:
      #print('read ' + filename)
      with open(label_path + '/' + filename) as f:
        lines = f.readlines()
      for line in lines:
        line = line.split('	')
        img = {
            'file_path': line[0],
            'detection_score': line[1],
            'captions': [caption_post_process(line[2])],
            'split': split,
            'modifiable': False
        }
        self.imgs += [img]
    print('Fashion200k:', len(self.imgs), 'images')

    # generate query for training or testing
    if split == 'train':
      self.caption_index_init_()
    else:
      self.generate_test_queries_()

  def get_different_word(self, source_caption, target_caption):
    source_words = source_caption.split()
    target_words = target_caption.split()
    for source_word in source_words:
      if source_word not in target_words:
        break
    for target_word in target_words:
      if target_word not in source_words:
        break
    mod_str = 'replace ' + source_word + ' with ' + target_word
    return source_word, target_word, mod_str

  def generate_test_queries_(self):
    file2imgid = {}
    for i, img in enumerate(self.imgs):
      file2imgid[img['file_path']] = i
    with open(self.img_path + '/test_queries.txt') as f:
      lines = f.readlines()
    self.test_queries = []
    for line in lines:
      source_file, target_file = line.split()
      idx = file2imgid[source_file]
      target_idx = file2imgid[target_file]
      source_caption = self.imgs[idx]['captions'][0]
      target_caption = self.imgs[target_idx]['captions'][0]
      source_word, target_word, mod_str = self.get_different_word(
          source_caption, target_caption)
      self.test_queries += [{
          'source_img_id': idx,
          'source_caption': source_caption,
          'target_caption': target_caption,
          'mod': {
              'str': mod_str
          }
      }]

  def caption_index_init_(self):
    """ index caption to generate training query-target example on the fly later"""

    # index caption 2 caption_id and caption 2 image_ids
    caption2id = {}
    id2caption = {}
    caption2imgids = {}
    for i, img in enumerate(self.imgs):
      for c in img['captions']:
        if c not in caption2id:
          id2caption[len(caption2id)] = c
          caption2id[c] = len(caption2id)
          caption2imgids[c] = []
        caption2imgids[c].append(i)
    self.caption2imgids = caption2imgids
    #print(len(caption2imgids), 'unique cations')

    # parent captions are 1-word shorter than their children
    parent2children_captions = {}
    for c in caption2id.keys():
      for w in c.split():
        p = c.replace(w, '')
        p = p.replace('  ', ' ').strip()
        if p not in parent2children_captions:
          parent2children_captions[p] = []
        if c not in parent2children_captions[p]:
          parent2children_captions[p].append(c)
    self.parent2children_captions = parent2children_captions

    # identify parent captions for each image
    for img in self.imgs:
      img['modifiable'] = False
      img['parent_captions'] = []
    for p in parent2children_captions:
      if len(parent2children_captions[p]) >= 2:
        for c in parent2children_captions[p]:
          for imgid in caption2imgids[c]:
            self.imgs[imgid]['modifiable'] = True
            self.imgs[imgid]['parent_captions'] += [p]
    num_modifiable_imgs = 0
    for img in self.imgs:
      if img['modifiable']:
        num_modifiable_imgs += 1
    #print('Modifiable images', num_modifiable_imgs)

  def caption_index_sample_(self, idx):
    while not self.imgs[idx]['modifiable']:
      idx = np.random.randint(0, len(self.imgs))

    # find random target image (same parent)
    img = self.imgs[idx]
    while True:
      p = random.choice(img['parent_captions'])
      c = random.choice(self.parent2children_captions[p])
      if c not in img['captions']:
        break
    target_idx = random.choice(self.caption2imgids[c])

    # find the word difference between query and target (not in parent caption)
    source_caption = self.imgs[idx]['captions'][0]
    target_caption = self.imgs[target_idx]['captions'][0]
    source_word, target_word, mod_str = self.get_different_word(
        source_caption, target_caption)
    return idx, target_idx, source_word, target_word, mod_str

  def get_all_texts(self):
    texts = []
    for img in self.imgs:
      for c in img['captions']:
        texts.append(c)
    return texts

  def __len__(self):
    return len(self.imgs)

  def __getitem__(self, idx):
    idx, target_idx, source_word, target_word, mod_str = self.caption_index_sample_(
        idx)
    out = {}
    out['source_img_id'] = idx
    out['source_img_data'] = self.get_img(idx)
    out['source_caption'] = self.imgs[idx]['captions'][0]
    out['target_img_id'] = target_idx
    out['target_img_data'] = self.get_img(target_idx)
    out['target_caption'] = self.imgs[target_idx]['captions'][0]
    out['mod'] = {'str': mod_str}
    return out

  def get_img(self, idx, raw_img=False):
    img_path = self.img_path + self.imgs[idx]['file_path']
    with open(img_path, 'rb') as f:
      img = PIL.Image.open(f)
      img = img.convert('RGB')
    if raw_img:
      return img
    if self.transform:
      img = self.transform(img)
    return img


class MITStates(BaseDataset):
  """MITStates dataset."""

  def __init__(self, path, split='train', transform=None):
    super(MITStates, self).__init__()
    self.path = path
    self.transform = transform
    self.split = split

    self.imgs = []
    test_nouns = [
        u'armor', u'bracelet', u'bush', u'camera', u'candy', u'castle',
        u'ceramic', u'cheese', u'clock', u'clothes', u'coffee', u'fan', u'fig',
        u'fish', u'foam', u'forest', u'fruit', u'furniture', u'garden', u'gate',
        u'glass', u'horse', u'island', u'laptop', u'lead', u'lightning',
        u'mirror', u'orange', u'paint', u'persimmon', u'plastic', u'plate',
        u'potato', u'road', u'rubber', u'sand', u'shell', u'sky', u'smoke',
        u'steel', u'stream', u'table', u'tea', u'tomato', u'vacuum', u'wax',
        u'wheel', u'window', u'wool'
    ]

    from os import listdir
    for f in listdir(path + '/images'):
      if ' ' not in f:
        continue
      adj, noun = f.split()
      if adj == 'adj':
        continue
      if split == 'train' and noun in test_nouns:
        continue
      if split == 'test' and noun not in test_nouns:
        continue

      for file_path in listdir(path + '/images/' + f):
        assert (file_path.endswith('jpg'))
        self.imgs += [{
            'file_path': path + '/images/' + f + '/' + file_path,
            'captions': [f],
            'adj': adj,
            'noun': noun
        }]

    self.caption_index_init_()
    if split == 'test':
      self.generate_test_queries_()

  def get_all_texts(self):
    texts = []
    for img in self.imgs:
      texts += img['captions']
    return texts

  def __getitem__(self, idx):
    try:
      self.saved_item
    except:
      self.saved_item = None
    if self.saved_item is None:
      while True:
        idx, target_idx1 = self.caption_index_sample_(idx)
        idx, target_idx2 = self.caption_index_sample_(idx)
        if self.imgs[target_idx1]['adj'] != self.imgs[target_idx2]['adj']:
          break
      idx, target_idx = [idx, target_idx1]
      self.saved_item = [idx, target_idx2]
    else:
      idx, target_idx = self.saved_item
      self.saved_item = None

    mod_str = self.imgs[target_idx]['adj']

    return {
        'source_img_id': idx,
        'source_img_data': self.get_img(idx),
        'source_caption': self.imgs[idx]['captions'][0],
        'target_img_id': target_idx,
        'target_img_data': self.get_img(target_idx),
        'target_caption': self.imgs[target_idx]['captions'][0],
        'mod': {
            'str': mod_str
        }
    }

  def caption_index_init_(self):
    self.caption2imgids = {}
    self.noun2adjs = {}
    for i, img in enumerate(self.imgs):
      cap = img['captions'][0]
      adj = img['adj']
      noun = img['noun']
      if cap not in self.caption2imgids.keys():
        self.caption2imgids[cap] = []
      if noun not in self.noun2adjs.keys():
        self.noun2adjs[noun] = []
      self.caption2imgids[cap].append(i)
      if adj not in self.noun2adjs[noun]:
        self.noun2adjs[noun].append(adj)
    for noun, adjs in self.noun2adjs.iteritems():
      assert len(adjs) >= 2

  def caption_index_sample_(self, idx):
    noun = self.imgs[idx]['noun']
    # adj = self.imgs[idx]['adj']
    target_adj = random.choice(self.noun2adjs[noun])
    target_caption = target_adj + ' ' + noun
    target_idx = random.choice(self.caption2imgids[target_caption])
    return idx, target_idx

  def generate_test_queries_(self):
    self.test_queries = []
    for idx, img in enumerate(self.imgs):
      adj = img['adj']
      noun = img['noun']
      for target_adj in self.noun2adjs[noun]:
        if target_adj != adj:
          mod_str = target_adj
          self.test_queries += [{
              'source_img_id': idx,
              'source_caption': adj + ' ' + noun,
              'target_caption': target_adj + ' ' + noun,
              'mod': {
                  'str': mod_str
              }
          }]
    print(len(self.test_queries), 'test queries')

  def __len__(self):
    return len(self.imgs)

  def get_img(self, idx, raw_img=False):
    img_path = self.imgs[idx]['file_path']
    with open(img_path, 'rb') as f:
      img = PIL.Image.open(f)
      img = img.convert('RGB')
    if raw_img:
      return img
    if self.transform:
      img = self.transform(img)
    return img

class Fashion200k(BaseDataset):
  """Fashion200k dataset."""

  def __init__(self, path, split='train', transform=None):
    super(Fashion200k, self).__init__()

    self.split = split
    self.transform = transform
    self.img_path = path + '/'

    # get label files for the split
    label_path = path + '/labels/'
    from os import listdir
    from os.path import isfile
    from os.path import join
    label_files = [
        f for f in listdir(label_path) if isfile(join(label_path, f))
    ]
    label_files = [f for f in label_files if split in f]

    label_files = [f for f in label_files if '._' not in f]

    # read image info from label files
    self.imgs = []

    def caption_post_process(s):
      return s.strip().replace('.',
                               'dotmark').replace('?', 'questionmark').replace(
                                   '&', 'andmark').replace('*', 'starmark')

    for filename in label_files:
      #print('read ' + filename)
      with open(label_path + '/' + filename , encoding='utf-8') as f:
        lines = f.readlines()
      for line in lines:
        line = line.split('	')
        img = {
            'file_path': line[0],
            'detection_score': line[1],
            'captions': [caption_post_process(line[2])],
            'split': split,
            'modifiable': False
        }
        self.imgs += [img]
    #print ('Test Fashion200k:', len(self.imgs), 'images')
    global testimagedata
    testimagedata=self.imgs
    # generate query for training or testing
    if split == 'train':
      self.caption_index_init_()
    else:
      self.generate_test_queries_()

  def get_different_word(self, source_caption, target_caption):
    source_words = source_caption.split()
    target_words = target_caption.split()
    for source_word in source_words:
      if source_word not in target_words:
        break
    for target_word in target_words:
      if target_word not in source_words:
        break
    mod_str = 'replace ' + source_word + ' with ' + target_word
    return source_word, target_word, mod_str

  def generate_test_queries_(self):
    file2imgid = {}
    for i, img in enumerate(self.imgs):
      file2imgid[img['file_path']] = i
    with open(self.img_path + '/test_queries.txt') as f:
      lines = f.readlines()
    self.test_queries = []
    for line in lines:
      source_file, target_file = line.split()
      idx = file2imgid[source_file]
      target_idx = file2imgid[target_file]
      source_caption = self.imgs[idx]['captions'][0]
      target_caption = self.imgs[target_idx]['captions'][0]
      source_word, target_word, mod_str = self.get_different_word(
          source_caption, target_caption)
      self.test_queries += [{
          'source_img_id': idx,
          'source_caption': source_caption,
          'target_caption': target_caption,
          'target_id':target_idx,
          'source_path':source_file,
          'target_path':target_file,
          # 'source_data':self.get_img(idx),
          # 'target_data':self.get_img(target_idx),
          'mod': {
              'str': mod_str
          }
      }]

  def caption_index_init_(self):
    """ index caption to generate training query-target example on the fly later"""

    # index caption 2 caption_id and caption 2 image_ids
    caption2id = {}
    id2caption = {}
    caption2imgids = {}
    for i, img in enumerate(self.imgs):
      for c in img['captions']:
        #if not caption2id.has_key(c):
        if c not in caption2id:
          id2caption[len(caption2id)] = c
          caption2id[c] = len(caption2id)
          caption2imgids[c] = []
        caption2imgids[c].append(i)
    self.caption2imgids = caption2imgids
    #print (len(caption2imgids), 'unique cations')

    # parent captions are 1-word shorter than their children
    parent2children_captions = {}
    for c in caption2id.keys():
      for w in c.split():
        p = c.replace(w, '')
        p = p.replace('  ', ' ').strip()
        #if not parent2children_captions.has_key(p):
        if p not in parent2children_captions:
          parent2children_captions[p] = []
        if c not in parent2children_captions[p]:
          parent2children_captions[p].append(c)
    self.parent2children_captions = parent2children_captions

    # identify parent captions for each image
    for img in self.imgs:
      img['modifiable'] = False
      img['parent_captions'] = []
    for p in parent2children_captions:
      if len(parent2children_captions[p]) >= 2:
        for c in parent2children_captions[p]:
          for imgid in caption2imgids[c]:
            self.imgs[imgid]['modifiable'] = True
            self.imgs[imgid]['parent_captions'] += [p]
    num_modifiable_imgs = 0
    for img in self.imgs:
      if img['modifiable']:
        num_modifiable_imgs += 1
    #print ('Modifiable images', num_modifiable_imgs)

  def caption_index_sample_(self, idx):
    while not self.imgs[idx]['modifiable']:
      idx = np.random.randint(0, len(self.imgs))

    # find random target image (same parent)
    img = self.imgs[idx]
    while True:
      p = random.choice(img['parent_captions'])
      c = random.choice(self.parent2children_captions[p])
      if c not in img['captions']:
        break
    target_idx = random.choice(self.caption2imgids[c])

    # find the word difference between query and target (not in parent caption)
    source_caption = self.imgs[idx]['captions'][0]
    target_caption = self.imgs[target_idx]['captions'][0]
    source_word, target_word, mod_str = self.get_different_word(
        source_caption, target_caption)
    return idx, target_idx, source_word, target_word, mod_str

  def source_caption_by_id(self, idx):
    source_caption = self.imgs[idx]['captions'][0]
    return source_caption

  def get_all_texts(self):
    texts = []
    for img in self.imgs:
      for c in img['captions']:
        texts.append(c)
    return texts

  def __len__(self):
    return len(self.imgs)

  def __getitem__(self, idx):
    idx, target_idx, source_word, target_word, mod_str = self.caption_index_sample_(
        idx)
    out = {}
    out['source_img_id'] = idx
    out['source_img_data'] = self.get_img(idx)
    out['source_caption'] = self.imgs[idx]['captions'][0]
    out['source_path'] = self.imgs[idx]['file_path']
    out['target_img_id'] = target_idx
    out['target_img_data'] = self.get_img(target_idx)
    out['target_caption'] = self.imgs[target_idx]['captions'][0]
    out['target_path'] = self.imgs[target_idx]['file_path']
    out['mod'] = {'str': mod_str}
    out['modifiable'] = self.imgs[idx]['modifiable']
    return out

  def get_img(self, idx, raw_img=False):
    img_path = self.img_path + self.imgs[idx]['file_path']
    with open(img_path, 'rb') as f:
      img = PIL.Image.open(f)
      img = img.convert('RGB')
    if raw_img:
      return img
    if self.transform:
      img = self.transform(img)
    return img

###### Get From File 
class Features172K():
  def __init__(self):
    super(Features172K, self).__init__()

  #Save Values of Features Of Train DataSet For Easy Access
  def SavetoFiles(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    for i in range(172048):#172048
      print('get images=',i,end='\r')
      item = testset[i]
      imgs += [item['source_img_data']]
      mods += [item['mod']['str']]
      if len(imgs) >= opt.batch_size or i == 9999:
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)
        f = model.compose_img_text(imgs, mods).data.cpu().numpy() #.cuda()
        all_queries += [f]
        imgs = []
        mods = []
      imgs0 += [item['target_img_data']]
      if len(imgs0) >= opt.batch_size or i == 9999:
        imgs0 = torch.stack(imgs0).float()
        imgs0 = torch.autograd.Variable(imgs0)
        imgs0 = model.extract_img_feature(imgs0).data.cpu().numpy() #.cuda()
        all_imgs += [imgs0]
        imgs0 = []
      all_captions += [item['target_caption']]
      all_target_captions += [item['target_caption']]
    all_imgs = np.concatenate(all_imgs)
    all_queries = np.concatenate(all_queries)

    with open(Path+r"/"+'Features172Kall_queries.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features172Kall_imgs.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)

    with open(Path+r"/"+'Features172Kall_captions.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)

  
  def SavetoFilesNoModule(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    for i in range(172048):#172048
      print('get images=',i,end='\r')
      item = testset[i]
      imgs += [item['source_img_data']]
      mods += [item['mod']['str']]
      if len(imgs) >= opt.batch_size or i == 9999:
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)
        f = model.compose_img_text(imgs, mods).data.cpu().numpy() #.cuda()
        all_queries += [f]
        imgs = []
        mods = []
      imgs0 += [item['target_img_data']]
      if len(imgs0) >= opt.batch_size or i == 9999:
        imgs0 = torch.stack(imgs0).float()
        imgs0 = torch.autograd.Variable(imgs0)
        imgs0 = model.extract_img_feature(imgs0).data.cpu().numpy() #.cuda()
        all_imgs += [imgs0]
        imgs0 = []
      all_captions += [item['target_caption']]
      all_target_captions += [item['target_caption']]
    all_imgs = np.concatenate(all_imgs)
    all_queries = np.concatenate(all_queries)

    with open(Path+r"/"+'Features172Kall_queriesNoModule.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features172Kall_imgsNoModule.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)

    with open(Path+r"/"+'Features172Kall_captionsNoModule.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)

  def SavetoFilesold(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    for i in range(172048):#172048
      print('get images=',i,end='\r')
      item = testset[i]
      imgs += [item['source_img_data']]
      mods += [item['mod']['str']]
      if len(imgs) >= opt.batch_size or i == 9999:
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)
        f = model.compose_img_text(imgs, mods).data.cpu().numpy() #.cuda()
        all_queries += [f]
        imgs = []
        mods = []
      imgs0 += [item['target_img_data']]
      if len(imgs0) >= opt.batch_size or i == 9999:
        imgs0 = torch.stack(imgs0).float()
        imgs0 = torch.autograd.Variable(imgs0)
        imgs0 = model.extract_img_feature(imgs0).data.cpu().numpy() #.cuda()
        all_imgs += [imgs0]
        imgs0 = []
      all_captions += [item['target_caption']]
      all_target_captions += [item['target_caption']]
    all_imgs = np.concatenate(all_imgs)
    all_queries = np.concatenate(all_queries)

    with open(Path+r"/"+'Features172Kall_queriesold.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features172Kall_imgsold.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)

    with open(Path+r"/"+'Features172Kall_captionsold.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)

  def SavetoFilesImageSource(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    for i in range(172048):#172048
      print('get images=',i,end='\r')
      item = testset[i]
      img1=testset[i]['source_img_data'].numpy()
      imgs += [img1]
    
    imgs = np.concatenate(imgs)

    with open(Path+r"/"+'Features172Kall_source.txt', 'wb') as fp:
      pickle.dump(imgs, fp)
  
  def SavetoFilesCaptionImages(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    for i in range(172048):#172048
      print('get images=',i,end='\r')
      item = testset[i]
      imgs = [item['source_caption']]
      imgs0= [item['target_caption']]

      f=model.extract_text_feature(imgs).data.cpu().numpy()
      f2=model.extract_text_feature(imgs0).data.cpu().numpy()
      all_captions += [f]
      all_target_captions += [f2]
      imgs=[]
      imgs0=[]


      
    all_captions = np.concatenate(all_captions)
    all_target_captions = np.concatenate(all_target_captions)

    with open(Path+r"/"+'Features172Kall_queriesphicaptions.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)

    with open(Path+r"/"+'Features172Kall_imgsphicaptions.txt', 'wb') as fp:
      pickle.dump(all_target_captions, fp)

    

    

   

  ################## Get Feature Extracted by Trig Model ############################ 

  def Get_all_queries(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_queries.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_images(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_imgs.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_captions(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_captions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data


  def Get_all_query_captions(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_queriesphicaptions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_target_captions(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_imgsphicaptions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data


  ################## Get Feature Extracted by Trig with out Model ############################ 

 ################## Get Feature Extracted by Resnet and LSTM Model ############################ 

  
  def Get_phix(self):
    with open (Path1+r"/dataset172/"+'Features172Kphix.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_phixtarget(self):
    with open (Path1+r"/dataset172/"+'Features172Kphixtarget.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_phit(self):
    with open (Path1+r"/dataset172/"+'Features172Kphit.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data



  ################## Get Feature Extracted by Trig with out Model ############################ 


  def Get_all_queriesWithoutModelTrig(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_queriesNoModule.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_imagesWithoutModelTrig(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_imgsNoModule.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_captionsWithoutModelTrig(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_captionsNoModule.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  def Get_phit_image_caption(self):
    with open (Path1+r"/phase2/"+'Features172Kall_queriesphicaptions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  
  def Get_semantic_query_caption(self):
    with open (Path1+r"/phase2/"+'semantic_query_caption.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  def Get_squery_caption_with_phix(self):
    with open (Path1+r"/phase2/"+'squery_with_phix.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_target_captions(self):
    with open (Path1+r"/phase2/"+'train_all_target_captions.txt', 'rb') as fp:
      all_target_captions = pickle.load(fp)
      return  all_target_captions



  
  ################# Get Feature Extracted by Trig Model  OLD One (Wrong ) ############################

  def Get_all_queriesold(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_queriesold.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  def Get_phit_image_caption(self):
    with open (Path1+r"/phase2/"+'Features172Kall_queriesphicaptions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  
  def Get_semantic_query_caption(self):
    with open (Path1+r"/phase2/"+'semantic_query_caption.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  def Get_squery_caption_with_phix(self):
    with open (Path1+r"/phase2/"+'squery_with_phix.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_target_captions(self):
    with open (Path1+r"/phase2/"+'train_all_target_captions.txt', 'rb') as fp:
      all_target_captions = pickle.load(fp)
      return  all_target_captions



  def Get_all_imagesold(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_imgsold.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_captionsold(self):
    with open (Path1+r"/dataset172/"+'Features172Kall_captionsold.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
 

class Features33K():
  def __init__(self):
    super(Features33K, self).__init__()

  #Save Values of Features Of Train DataSet For Easy Access
  def SavetoFiles(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      imgs += [testset.get_img(t['source_img_id'])]
      mods += [t['mod']['str']]
      if len(imgs) >= opt.batch_size or t is test_queries[-1]:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        f = model.compose_img_text(imgs, mods).data.cpu().numpy()
        all_queries += [f]
        imgs = []
        mods = []
    all_queries = np.concatenate(all_queries)
    all_target_captions = [t['target_caption'] for t in test_queries]

    # compute all image features
    imgs = []
    for i in tqdm(range(len(testset.imgs))):
      imgs += [testset.get_img(i)]
      if len(imgs) >= opt.batch_size or i == len(testset.imgs) - 1:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        imgs = model.extract_img_feature(imgs).data.cpu().numpy()
        all_imgs += [imgs]
        imgs = []
    all_imgs = np.concatenate(all_imgs)
    all_captions = [img['captions'][0] for img in testset.imgs]

    with open(Path+r"/"+'Features33Kall_queries.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features33Kall_imgs.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)

    with open(Path+r"/"+'Features33Kall_captions.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)
    
    with open(Path+r"/"+'Features33Kall_target_captions.txt', 'wb') as fp:
      pickle.dump(all_target_captions, fp)

  




  def SavetoFilesCaptionImages(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      
      imgs = [t['source_caption']]
      imgs0 = [t['target_caption']]
      f=model.extract_text_feature(imgs).data.cpu().numpy()
      f2=model.extract_text_feature(imgs0).data.cpu().numpy()
      all_captions += [f]
      all_target_captions += [f2]
      imgs=[]
      imgs0=[]


      
    all_captions = np.concatenate(all_captions)
    all_target_captions = np.concatenate(all_target_captions)



    
    with open(Path+r"/"+'Features33Kall_queriesphicaptions.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)

    with open(Path+r"/"+'Features33Kall_imgsphicaptions.txt', 'wb') as fp:
      pickle.dump(all_target_captions, fp)
    
  def SavetoFilesNoModule(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      imgs += [testset.get_img(t['source_img_id'])]
      mods += [t['mod']['str']]
      if len(imgs) >= opt.batch_size or t is test_queries[-1]:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        f = model.compose_img_text(imgs, mods).data.cpu().numpy()
        all_queries += [f]
        imgs = []
        mods = []
    all_queries = np.concatenate(all_queries)
    all_target_captions = [t['target_caption'] for t in test_queries]

    # compute all image features
    imgs = []
    for i in tqdm(range(len(testset.imgs))):
      imgs += [testset.get_img(i)]
      if len(imgs) >= opt.batch_size or i == len(testset.imgs) - 1:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        imgs = model.extract_img_feature(imgs).data.cpu().numpy()
        all_imgs += [imgs]
        imgs = []
    all_imgs = np.concatenate(all_imgs)
    all_captions = [img['captions'][0] for img in testset.imgs]

    with open(Path+r"/"+'Features33Kall_queriesNoModule.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features33Kall_imgsNoModule.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)

    with open(Path+r"/"+'Features33Kall_captionsNoModule.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)
    
    with open(Path+r"/"+'Features33Kall_target_captionsNoModule.txt', 'wb') as fp:
      pickle.dump(all_target_captions, fp)

  def SavetoFilesold(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      imgs += [testset.get_img(t['source_img_id'])]
      mods += [t['mod']['str']]
      if len(imgs) >= opt.batch_size or t is test_queries[-1]:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        f = model.compose_img_text(imgs, mods).data.cpu().numpy()
        all_queries += [f]
        imgs = []
        mods = []
    all_queries = np.concatenate(all_queries)
    all_target_captions = [t['target_caption'] for t in test_queries]

    # compute all image features
    imgs = []
    for i in tqdm(range(len(testset.imgs))):
      imgs += [testset.get_img(i)]
      if len(imgs) >= opt.batch_size or i == len(testset.imgs) - 1:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        imgs = model.extract_img_feature(imgs).data.cpu().numpy()
        all_imgs += [imgs]
        imgs = []
    all_imgs = np.concatenate(all_imgs)
    all_captions = [img['captions'][0] for img in testset.imgs]

    with open(Path+r"/"+'Features33Kall_queriesold.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features33Kall_imgsold.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)

    with open(Path+r"/"+'Features33Kall_captionsold.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)
    
    with open(Path+r"/"+'Features33Kall_target_captionsold.txt', 'wb') as fp:
      pickle.dump(all_target_captions, fp)

  def SavetoFiles2(self,Path,model,testset,opt):
    model.eval()
    target = []
    all_target = []
    
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      target +=[testset.get_img(t['target_id'])]
      target = torch.stack(target).float()
      target = torch.autograd.Variable(target)
      f2 = model.extract_img_feature(target).data.cpu().numpy()
      all_target += [f2]
      target=[]
    all_target = np.concatenate(all_target)

    

    with open(Path+r"/"+'Features33Kall_target.txt', 'wb') as fp:
      pickle.dump(all_target, fp)

  def SavetoFiles3(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []

    imgs0 = []
    imgs = []
    mods = []
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      imgs += [testset.get_img(t['source_img_id'])]
      mods += [t['mod']['str']]
      if len(imgs) >= opt.batch_size or t is test_queries[-1]:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        #f = model.compose_img_text(imgs, mods).data.cpu().numpy()
        f = model.extract_img_feature(imgs).data.cpu().numpy()
        all_queries += [f]
        imgs = []
        mods = []
    all_queries = np.concatenate(all_queries)
    
    
    with open(Path+r"/"+'Features33Kallsource_imgfeature.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

  


  ################## Get Feature Extracted by Trig Model ############################ 


  def Get_all_queries(self):
      with open (Path1+r"/dataset33/"+'Features33Kall_queries.txt', 'rb') as fp:
        data = pickle.load(fp) 
        return data

  def Get_all_images(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_imgs.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_captions(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_captions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  
  def Get_target_captions(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_target_captions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

 ################## Get Feature Extracted by Resnet and LSTM Model ############################ 

  
  def Get_phix(self):
    with open (Path1+r"/dataset33/"+'Features33Kphix.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_phixtarget(self):
    with open (Path1+r"/dataset33/"+'Features33Kphixtarget.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_phit(self):
    with open (Path1+r"/dataset33/"+'Features33Kphit.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  
  def Get_all_query_captions(self):
    with open (Path1+r"/dataset172/"+'Features33Kall_queriesphicaptions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_target_captions(self):
    with open (Path1+r"/dataset172/"+'Features33Kall_imgsphicaptions.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  ################## Get Feature Extracted by Trig with out Model ############################ 


  def Get_all_queriesWithoutModelTrig(self):
      with open (Path1+r"/dataset33/"+'Features33Kall_queriesNoModule.txt', 'rb') as fp:
        data = pickle.load(fp) 
        return data

  def Get_all_imagesWithoutModelTrig(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_imgsNoModule.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_captionsWithoutModelTrig(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_captionsNoModule.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  
  def Get_target_captionsWithoutModelTrig(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_target_captionsNoModule.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data


  ################## Get Feature Extracted by Resnet and LSTM Model for all 33K ############################ 


  def Get_all_target(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_target.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_source_imgafeatured(self):
      with open (Path1+r"/dataset33/"+'Features33Kallsource_imgfeature.txt', 'rb') as fp:
        data = pickle.load(fp) 
        return data



  
  ################# Old Model of trig (wrong one)

  def Get_all_queriesold(self):
      with open (Path1+r"/dataset33/"+'Features33Kall_queriesold.txt', 'rb') as fp:
        data = pickle.load(fp) 
        return data

  def Get_all_imagesold(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_imgsold.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

  def Get_all_captionsold(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_captionsold.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data
  
  def Get_target_captionsold(self):
    with open (Path1+r"/dataset33/"+'Features33Kall_target_captionsold.txt', 'rb') as fp:
      data = pickle.load(fp) 
      return data

################# Get Img and Text Features Without Tirg
class Feature172KOrg():
  def __init__(self):
    super(Feature172KOrg, self).__init__()
    
    if(os.path.isdir(Path1+r"/dataset172Org/")):

      with open (Path1+r"/dataset172Org/"+'Features172KphixQuery.txt', 'rb') as fp:
        self.PhixQueryImg = pickle.load(fp) 
      
      with open (Path1+r"/dataset172Org/"+'Features172KphitQueryCaption.txt', 'rb') as fp:
        self.PhitQueryCaption = pickle.load(fp) 

      with open (Path1+r"/dataset172Org/"+'Features172KphitQueryMod.txt', 'rb') as fp:
        self.PhitQueryMod = pickle.load(fp) 
      
      with open (Path1+r"/dataset172Org/"+'Features172KphixTarget.txt', 'rb') as fp:
        self.PhixTargetImg = pickle.load(fp) 

      with open (Path1+r"/dataset172Org/"+'Features172KphitTargetCaption.txt', 'rb') as fp:
        self.PhitTargetCaption = pickle.load(fp) 

      with open(Path1+r"/dataset172Org/"+'Features172Kall_captions_text.txt', 'rb') as fp:
        self.all_captions_text = pickle.load(fp) 

      with open(Path1+r"/dataset172Org/"+'Features172Kall_target_captions_text.txt', 'rb') as fp:
        self.all_target_captions_text = pickle.load(fp) 

      with open(Path1+r"/dataset172Org/"+'Features172Kall_Query_captions_text.txt', 'rb') as fp:
        self.all_Query_captions_text = pickle.load(fp) 

      with open(Path1+r"/dataset172Org/"+'Features172Kall_ids.txt', 'rb') as fp:
        self.all_ids = pickle.load(fp) 

  def SavetoFilesphixt(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_queries = []
    all_target_captions = []
    all_Query_captions = []
    all_captions_text = []
    all_ids = []
    all_target_captions_text = []
    all_Query_captions_text = []

    imgs0 = []
    imgs = []
    mods = []
    text0=[]
    text1=[]
    for i in range(172048):#172048  source_caption
      item = testset[i]
      idx = {
          'source_img_id': item['source_img_id'],
          'target_id':item['target_img_id']          
      }
      print('get images=',i,end='\r')
      
      imgs += [item['source_img_data']]
      mods += [item['mod']['str']]
      if len(imgs) >= opt.batch_size or i == 9999:
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)
        f = model.extract_img_feature(imgs).data.cpu().numpy() #.cuda()
        f2 = model.extract_text_feature(mods).data.cpu().numpy() #.cuda()
        text1 = model.extract_text_feature([item['source_caption']]).data.cpu().numpy() #.cuda()
        all_queries += [f]
        all_captions += [f2]
        all_captions_text +=[mods]
        all_Query_captions += [text1]
        all_Query_captions_text += [[item['source_caption']]]
        all_ids += [idx]

        imgs = []
        mods = []
        text1 = []
        
      imgs0 += [item['target_img_data']]
      if len(imgs0) >= opt.batch_size or i == 9999:
        imgs0 = torch.stack(imgs0).float()
        imgs0 = torch.autograd.Variable(imgs0)
        imgs0 = model.extract_img_feature(imgs0).data.cpu().numpy() #.cuda()
        text0 = model.extract_text_feature([item['target_caption']]).data.cpu().numpy()
        all_imgs += [imgs0]
        imgs0 = []
        all_target_captions += [text0]
        all_target_captions_text += [[item['target_caption']]]
        text0 = []

    all_imgs = np.concatenate(all_imgs)
    all_queries = np.concatenate(all_queries)
    all_captions = np.concatenate(all_captions)
    all_target_captions = np.concatenate(all_target_captions)
    all_Query_captions = np.concatenate(all_Query_captions)
    # all_captions_text = np.concatenate(all_captions_text)
    # all_target_captions_text = np.concatenate(all_target_captions_text)
    # all_Query_captions_text = np.concatenate(all_Query_captions_text)
    
    if(not os.path.isdir(Path1+r"/dataset172Org/")):
      os.makedirs(Path1+r"/dataset172Org/")


    with open(Path+r"/"+'Features172KphixQuery.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features172KphitQueryMod.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)

    with open(Path+r"/"+'Features172KphixTarget.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)

    with open(Path+r"/"+'Features172KphitTargetCaption.txt', 'wb') as fp:
      pickle.dump(all_target_captions, fp)

    with open(Path+r"/"+'Features172KphitQueryCaption.txt', 'wb') as fp:
      pickle.dump(all_Query_captions, fp)

    with open(Path+r"/"+'Features172Kall_captions_text.txt', 'wb') as fp:
      pickle.dump(all_captions_text, fp)

    with open(Path+r"/"+'Features172Kall_target_captions_text.txt', 'wb') as fp:
      pickle.dump(all_target_captions_text, fp)

    with open(Path+r"/"+'Features172Kall_Query_captions_text.txt', 'wb') as fp:
      pickle.dump(all_Query_captions_text, fp)
    
    with open(Path+r"/"+'Features172Kall_ids.txt', 'wb') as fp:
      pickle.dump(all_ids, fp)

class Features33KOrg():
  def __init__(self):
    super(Features33KOrg, self).__init__()

    if(os.path.isdir(Path1+r"/dataset33Org/")):
    
      with open (Path1+r"/dataset33Org/"+'Features33KphixQuery.txt', 'rb') as fp:
        self.PhixQueryImg = pickle.load(fp) 
      
      with open (Path1+r"/dataset33Org/"+'Features33KphitQueryCaption.txt', 'rb') as fp:
        self.PhitQueryCaption = pickle.load(fp) 

      with open (Path1+r"/dataset33Org/"+'Features33KphitQueryMod.txt', 'rb') as fp:
        self.PhitQueryMod = pickle.load(fp) 
      
      with open (Path1+r"/dataset33Org/"+'Features33KphixTarget.txt', 'rb') as fp:
        self.PhixTargetImg = pickle.load(fp) 

      with open (Path1+r"/dataset33Org/"+'Features33KphitTargetCaption.txt', 'rb') as fp:
        self.PhitTargetCaption = pickle.load(fp) 
      
      with open (Path1+r"/dataset33Org/"+'Features33KphixTestDatasetImg.txt', 'rb') as fp:
        self.PhixAllImages = pickle.load(fp) 

      with open (Path1+r"/dataset33Org/"+'Features33KphitTestDatasetImg.txt', 'rb') as fp:
        self.PhitAllImagesCaptions = pickle.load(fp) 
      
      with open(Path1+r"/dataset33Org/"+'Features33Kall_captions_text.txt', 'rb') as fp:
        self.all_captions_text = pickle.load(fp)

      with open(Path1+r"/dataset33Org/"+'Features33Kall_target_captions_text.txt', 'rb') as fp:
        self.all_target_captions_text = pickle.load(fp)

      with open(Path1+r"/dataset33Org/"+'Features33Kall_queries_captions_text.txt', 'rb') as fp:
        self.all_queries_captions_text = pickle.load(fp)
      
      with open(Path1+r"/dataset33Org/"+'Features33Kall_queries_Mod_text.txt', 'rb') as fp:
        self.all_queries_Mod_text = pickle.load(fp)
  
      with open(Path1+r"/dataset33Org/"+'Features33Kall_ids.txt', 'rb') as fp:
        self.all_ids = pickle.load(fp)

    
  
  def SavetoFilesphixt(self,Path,model,testset,opt):
    model.eval()
    all_imgs = []
    all_captions = []
    all_target = []
    all_target_captions = []
    all_queries = []
    all_queries_captions = []
    all_queries_Mod = []
    all_captions_text = []
    all_target_captions_text = []
    all_queries_captions_text = []
    all_queries_Mod_text = []
    all_ids = []

    imgs0 = []
    imgs = []
    mods = []
    target=[]
    Qcaption=[]
    Tcaption=[]
    
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      idx = {
          'source_img_id': t['source_img_id'],
          'target_id':t['target_id']          
      }
      imgs += [testset.get_img(t['source_img_id'])]
      mods += [t['mod']['str']]
      target += [testset.get_img(t['target_id'])]
      Qcaption += [t['source_caption']]
      Tcaption += [t['target_caption']]
      all_queries_captions_text += [t['source_caption']]
      all_target_captions_text += [t['target_caption']]
      all_queries_Mod_text += [t['mod']['str']]

      if len(imgs) >= opt.batch_size or t is test_queries[-1]:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
          target = [torch.from_numpy(d).float() for d in target]

        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)
        target = torch.stack(target).float()
        target = torch.autograd.Variable(target)

        f = model.extract_img_feature(imgs).data.cpu().numpy() 
        f2 = model.extract_text_feature(mods).data.cpu().numpy()
        f3 = model.extract_img_feature(target).data.cpu().numpy()
        f4 = model.extract_text_feature(Qcaption).data.cpu().numpy()
        f5 = model.extract_text_feature(Tcaption).data.cpu().numpy()

        all_queries += [f]
        all_queries_Mod += [f2]
        all_target += [f3]
        all_queries_captions += [f4]
        all_target_captions += [f5]
        all_ids += [idx]

        imgs = []
        mods = []
        target=[]
        Qcaption=[]
        Tcaption=[]
    
    all_target = np.concatenate(all_target)
    all_target_captions = np.concatenate(all_target_captions)
    all_queries = np.concatenate(all_queries)
    all_queries_captions = np.concatenate(all_queries_captions)
    all_queries_Mod = np.concatenate(all_queries_Mod)
    #all_target_captions = [t['target_caption'] for t in test_queries]

    # compute all image features  
    imgs = []
    imgsCaption = []

    for i in tqdm(range(len(testset.imgs))):
      imgs += [testset.get_img(i)]
      if len(imgs) >= opt.batch_size or i == len(testset.imgs) - 1:
        if 'torch' not in str(type(imgs[0])):
          imgs = [torch.from_numpy(d).float() for d in imgs]
        imgs = torch.stack(imgs).float()
        imgs = torch.autograd.Variable(imgs)#.cuda()
        imgs = model.extract_img_feature(imgs).data.cpu().numpy()
        imgsCaption = model.extract_text_feature(testset.imgs[i]['captions']).data.cpu().numpy()
        all_captions_text += [testset.imgs[i]['captions']]

        all_imgs += [imgs]
        all_captions += [imgsCaption]
        imgs = []
        imgsCaption = []
    all_imgs = np.concatenate(all_imgs)
    all_captions = np.concatenate(all_captions)

    if(not os.path.isdir(Path1+r"/dataset33Org/")):
      os.makedirs(Path1+r"/dataset33Org/")

    with open(Path+r"/"+'Features33KphixQuery.txt', 'wb') as fp:
      pickle.dump(all_queries, fp)

    with open(Path+r"/"+'Features33KphitQueryMod.txt', 'wb') as fp:
      pickle.dump(all_queries_Mod, fp)

    with open(Path+r"/"+'Features33KphixTarget.txt', 'wb') as fp:
      pickle.dump(all_target, fp)

    with open(Path+r"/"+'Features33KphitQueryCaption.txt', 'wb') as fp:
      pickle.dump(all_queries_captions, fp)

    with open(Path+r"/"+'Features33KphitTargetCaption.txt', 'wb') as fp:
      pickle.dump(all_target_captions, fp)

    with open(Path+r"/"+'Features33KphixTestDatasetImg.txt', 'wb') as fp:
      pickle.dump(all_imgs, fp)
    
    with open(Path+r"/"+'Features33KphitTestDatasetImg.txt', 'wb') as fp:
      pickle.dump(all_captions, fp)

    with open(Path+r"/"+'Features33Kall_captions_text.txt', 'wb') as fp:
      pickle.dump(all_captions_text, fp)

    with open(Path+r"/"+'Features33Kall_target_captions_text.txt', 'wb') as fp:
      pickle.dump(all_target_captions_text, fp)

    with open(Path+r"/"+'Features33Kall_queries_captions_text.txt', 'wb') as fp:
      pickle.dump(all_queries_captions_text, fp)
    
    with open(Path+r"/"+'Features33Kall_queries_Mod_text.txt', 'wb') as fp:
      pickle.dump(all_queries_Mod_text, fp)

    with open(Path+r"/"+'Features33Kall_ids.txt', 'wb') as fp:
      pickle.dump(all_ids, fp)

class Features152Org():
  def __init__(self):
    super(Features152Org, self).__init__()
    
    with open (Path1+r"/dataset152Org/"+'phix_152.txt', 'rb') as fp:
      self.phix_152 = pickle.load(fp) 
    
    with open (Path1+r"/dataset152Org/"+'target_phix_152.txt', 'rb') as fp:
      self.target_phix_152 = pickle.load(fp) 

    with open (Path1+r"/dataset152Org/"+'phix_152_test.txt', 'rb') as fp:
      self.phix_152_test = pickle.load(fp) 
    
    with open (Path1+r"/dataset152Org/"+'target_phix_152_test.txt', 'rb') as fp:
      self.target_phix_152_test = pickle.load(fp) 

class Features50Org():
  def __init__(self):
    super(Features50Org, self).__init__()
    
    with open (Path1+r"/dataset50Org/"+'phix_50.txt', 'rb') as fp:
      self.phix_50 = pickle.load(fp) 
    
    with open (Path1+r"/dataset50Org/"+'target_phix_50.txt', 'rb') as fp:
      self.target_phix_50 = pickle.load(fp) 

    with open (Path1+r"/dataset50Org/"+'phix_50_test.txt', 'rb') as fp:
      self.phix_50_test = pickle.load(fp) 
    
    with open (Path1+r"/dataset50Org/"+'target_phix_50_test.txt', 'rb') as fp:
      self.target_phix_50_test = pickle.load(fp) 

##################  Get Img & text Without Random Selection 

class Feature172KImgTextF():
  def __init__(self):
    super(Feature172KImgTextF, self).__init__()
  
  def SaveFeaturestoFile(self,Path):
    train = datasets.Fashion200k(
        path=Path1,
        split='train',
        transform=torchvision.transforms.Compose([
            torchvision.transforms.Resize(224),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize([0.485, 0.456, 0.406],
                                              [0.229, 0.224, 0.225])
        ]))
    
    trig= img_text_composition_models.TIRG([t.encode().decode('utf-8') for t in train.get_all_texts()],512)
    trig.load_state_dict(torch.load(Path1+r'\fashion200k.tirg.iter160k.pth' , map_location=torch.device('cpu') )['model_state_dict'])
    trig.eval()
    opt = argparse.ArgumentParser()
    opt.add_argument('--batch_size', type=int, default=2)
    opt.add_argument('--dataset', type=str, default='fashion200k')
    opt.batch_size =1
    opt.dataset='fashion200k'


    if(os.path.exists(Path+r'/Feature172Info.txt')):
      print('172K Index File already found... begining of Extracting Features ')
    else:
      self.SavetoFilesQueryidx(Path,train)
      print('172K Index File Created')

    self.SaveExtractedFeaturesToFilesModelTirg(Path,trig,train)
    print('Some 172K Features Has been extracted, working on the rest. ')
    self.SaveImgFeature1525018(Path,train)
    print('Done for 172K Features ')

  def SavetoFilesQueryidx(self,Path,testset):
    model.eval()    
    QueryInfo=[]
    for i in range(172048):#172048
      print('Extracting Feature From image=',i,end='\r')  
      item = testset[i]
      idx = {
          'QueryID': item['source_img_id'],
          'TargetID':item['target_img_id'],
          'Mod':  item['mod']['str'],
          'QueryCaption':item['source_caption'],
          'TargetCaption':item['target_caption'],
          'QueryURL':item['source_path'],
          'TargetURL':item['target_path']
      }
      QueryInfo += [idx]
      
    
    if(not os.path.isdir(Path)):
      os.makedirs(Path)
    
    with open(Path+r"/"+'Feature172Info.txt', 'wb') as fp:
      pickle.dump(QueryInfo, fp)

  def SaveExtractedFeaturesToFilesModelTirg(self,Path,model,testset):
    if(os.path.isdir(Path)):

      with open (Path+r'/Feature172Info.txt', 'rb') as fp:
        QueryInfo = pickle.load(fp) 

      QueryImgFeatures=[]
      ModTextFeature=[]
      QueryTextFeature=[]
      TargetImgFeatures=[]
      TargetTextFeature=[]
            
      for item in tqdm(QueryInfo):      
        QueryImgFeatures += [model.extract_img_feature(torch.stack([testset.get_img(item['QueryID'])]).float()).data.cpu().numpy()]
        ModTextFeature += [model.extract_text_feature([item['Mod']]).data.cpu().numpy()]
        QueryTextFeature += [model.extract_text_feature([item['QueryCaption']]).data.cpu().numpy()]
        TargetImgFeatures += [model.extract_img_feature(torch.stack([testset.get_img(item['TargetID'])]).float()).data.cpu().numpy()]
        TargetTextFeature += [model.extract_text_feature([item['TargetCaption']]).data.cpu().numpy()]

      QueryImgFeatures=np.concatenate(QueryImgFeatures)
      ModTextFeature=np.concatenate(ModTextFeature)
      QueryTextFeature=np.concatenate(QueryTextFeature)
      TargetImgFeatures=np.concatenate(TargetImgFeatures)
      TargetTextFeature=np.concatenate(TargetTextFeature)

      with open(Path+r"/"+'Feature172QueryImgTrigModel.txt', 'wb') as fp:
        pickle.dump(QueryImgFeatures, fp)

      with open(Path+r"/"+'Feature172ModTrigModel.txt', 'wb') as fp:
        pickle.dump(ModTextFeature, fp)

      with open(Path+r"/"+'Feature172CaptionQueryTrigModel.txt', 'wb') as fp:
        pickle.dump(QueryTextFeature, fp)

      with open(Path+r"/"+'Feature172TargetImgTrigModel.txt', 'wb') as fp:
        pickle.dump(TargetImgFeatures, fp)

      with open(Path+r"/"+'Feature172CaptionTargetTrigModel.txt', 'wb') as fp:
        pickle.dump(TargetTextFeature, fp)

  def SaveImgFeature1525018(self,Path,testset):
    Resnet152 = models.resnet152(pretrained=True)
    Resnet152.fc = nn.Identity()
    Resnet152.eval()

    Resnet50 = models.resnet50(pretrained=True)
    Resnet50.fc = nn.Identity()
    Resnet50.eval()

    Resnet18 = models.resnet18(pretrained=True)
    Resnet18.fc = nn.Identity()
    Resnet18.eval()

    if(os.path.isdir(Path)):

      with open (Path+r'/Feature172Info.txt', 'rb') as fp:
        QueryInfo = pickle.load(fp) 
            
      for item in tqdm(QueryInfo):      
        QueryImgFeature152=[]
        QueryImgFeature50=[]
        QueryImgFeature18=[]
        TargetImgFeature152=[]
        TargetImgFeature50=[]
        TargetImgFeature18=[]

        img=testset.get_img(item['QueryID'])
        img=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))

        Target=testset.get_img(item['TargetID'])
        Target=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))


        out=Resnet152(img)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        QueryImgFeature152 +=[out[0,:]]

        out=Resnet50(img)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        QueryImgFeature50 +=[out[0,:]]

        out=Resnet18(img)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        QueryImgFeature18 +=[out[0,:]]

        #########################################
        out=Resnet152(Target)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        TargetImgFeature152 +=[out[0,:]]

        out=Resnet50(Target)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        TargetImgFeature50 +=[out[0,:]]

        out=Resnet18(Target)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        TargetImgFeature18 +=[out[0,:]]

      with open(Path+r"/"+'Feature172QueryImg152.txt', 'wb') as fp:
          pickle.dump(QueryImgFeature152, fp)

      with open(Path+r"/"+'Feature172QueryImg50.txt', 'wb') as fp:
        pickle.dump(QueryImgFeature50, fp)

      with open(Path+r"/"+'Feature172QueryImg18.txt', 'wb') as fp:
        pickle.dump(QueryImgFeature18, fp)

      with open(Path+r"/"+'Feature172TargetImg152.txt', 'wb') as fp:
        pickle.dump(TargetImgFeature152, fp)

      with open(Path+r"/"+'Feature172TargetImg50.txt', 'wb') as fp:
        pickle.dump(TargetImgFeature50, fp)

      with open(Path+r"/"+'Feature172TargetImg18.txt', 'wb') as fp:
        pickle.dump(TargetImgFeature18, fp)

class Feature33KImgTextF():
  def __init__(self):
      super(Feature33KImgTextF, self).__init__()
  
  def SaveFeaturestoFile(self,Path):

    train = datasets.Fashion200k(
        path=Path1,
        split='train',
        transform=torchvision.transforms.Compose([
            torchvision.transforms.Resize(224),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize([0.485, 0.456, 0.406],
                                              [0.229, 0.224, 0.225])
        ]))
    
    test = datasets.Fashion200k(
        path=Path1,
        split='test',
        transform=torchvision.transforms.Compose([
            torchvision.transforms.Resize(224),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize([0.485, 0.456, 0.406],
                                              [0.229, 0.224, 0.225])
        ]))
    
    trig= img_text_composition_models.TIRG([t.encode().decode('utf-8') for t in train.get_all_texts()],512)
    trig.load_state_dict(torch.load(Path1+r'\fashion200k.tirg.iter160k.pth' , map_location=torch.device('cpu') )['model_state_dict'])
    trig.eval()
    opt = argparse.ArgumentParser()
    opt.add_argument('--batch_size', type=int, default=2)
    opt.add_argument('--dataset', type=str, default='fashion200k')
    opt.batch_size =1
    opt.dataset='fashion200k'


    if(os.path.exists(Path+r'/Feature33Info.txt')):
      print('33K Index File already found... begining of Extracting Features ')
    else:
      self.SavetoFilesQueryidx(Path,test)
      print('33K Index File Created')

    self.SaveExtractedFeaturesToFilesModelTirg(Path,trig,test)
    print('Some 33K Features Has been extracted, working on the rest. ')
    self.SaveImgFeature1525018(Path,test)
    print('Done for 33K Features ')

  def SavetoFilesQueryidx(self,Path,model,testset,opt):
    model.eval()
    QueryInfo=[]
    
    
    test_queries = testset.get_test_queries()
    for t in tqdm(test_queries):
      idx = {
          
          'QueryID': t['source_img_id'],
          'TargetID':t['target_id'],
          'Mod':  t['mod']['str'],
          'QueryCaption':t['source_caption'],
          'TargetCaption':t['target_caption'],
          'QueryURL':t['source_path'],
          'TargetURL':t['target_path']         
      }
      QueryInfo += [idx]

    # compute all image features  
    

    if(not os.path.isdir(Path)):
      os.makedirs(Path)

    with open(Path+r"/"+'Feature33Info.txt', 'wb') as fp:
      pickle.dump(QueryInfo, fp)
   
  def SaveExtractedFeaturesToFilesModelTirg(self,Path,model,testset):
    if(os.path.isdir(Path)):

      with open (Path+r'/Feature33Info.txt', 'rb') as fp:
        QueryInfo = pickle.load(fp) 

      QueryImgFeatures=[]
      ModTextFeature=[]
      QueryTextFeature=[]
      TargetImgFeatures=[]
      TargetTextFeature=[]
            
      for item in tqdm(QueryInfo):      
        QueryImgFeatures += [model.extract_img_feature(torch.stack([testset.get_img(item['QueryID'])]).float()).data.cpu().numpy()]
        ModTextFeature += [model.extract_text_feature([item['Mod']]).data.cpu().numpy()]
        QueryTextFeature += [model.extract_text_feature([item['QueryCaption']]).data.cpu().numpy()]
        TargetImgFeatures += [model.extract_img_feature(torch.stack([testset.get_img(item['TargetID'])]).float()).data.cpu().numpy()]
        TargetTextFeature += [model.extract_text_feature([item['TargetCaption']]).data.cpu().numpy()]

      QueryImgFeatures=np.concatenate(QueryImgFeatures)
      ModTextFeature=np.concatenate(ModTextFeature)
      QueryTextFeature=np.concatenate(QueryTextFeature)
      TargetImgFeatures=np.concatenate(TargetImgFeatures)
      TargetTextFeature=np.concatenate(TargetTextFeature)

      with open(Path+r"/"+'Feature33QueryImgTrigModel.txt', 'wb') as fp:
        pickle.dump(QueryImgFeatures, fp)

      with open(Path+r"/"+'Feature33ModTrigModel.txt', 'wb') as fp:
        pickle.dump(ModTextFeature, fp)

      with open(Path+r"/"+'Feature33CaptionQueryTrigModel.txt', 'wb') as fp:
        pickle.dump(QueryTextFeature, fp)

      with open(Path+r"/"+'Feature33TargetImgTrigModel.txt', 'wb') as fp:
        pickle.dump(TargetImgFeatures, fp)

      with open(Path+r"/"+'Feature33CaptionTargetTrigModel.txt', 'wb') as fp:
        pickle.dump(TargetTextFeature, fp)

  def SaveImgFeature1525018(self,Path,testset):
    Resnet152 = models.resnet152(pretrained=True)
    Resnet152.fc = nn.Identity()
    Resnet152.eval()

    Resnet50 = models.resnet50(pretrained=True)
    Resnet50.fc = nn.Identity()
    Resnet50.eval()

    Resnet18 = models.resnet18(pretrained=True)
    Resnet18.fc = nn.Identity()
    Resnet18.eval()

    if(os.path.isdir(Path)):

      with open (Path1+r'/Feature172Info.txt', 'rb') as fp:
        QueryInfo = pickle.load(fp) 
            
      for item in tqdm(QueryInfo):      
        QueryImgFeature152=[]
        QueryImgFeature50=[]
        QueryImgFeature18=[]
        TargetImgFeature152=[]
        TargetImgFeature50=[]
        TargetImgFeature18=[]

        img=testset.get_img(item['QueryID'])
        img=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))

        Target=testset.get_img(item['TargetID'])
        Target=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))


        out=Resnet152(img)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        QueryImgFeature152 +=[out[0,:]]

        out=Resnet50(img)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        QueryImgFeature50 +=[out[0,:]]

        out=Resnet18(img)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        QueryImgFeature18 +=[out[0,:]]

        #########################################
        out=Resnet152(Target)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        TargetImgFeature152 +=[out[0,:]]

        out=Resnet50(Target)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        TargetImgFeature50 +=[out[0,:]]

        out=Resnet18(Target)
        out = Variable(out, requires_grad=False)
        out=np.array(out)
        TargetImgFeature18 +=[out[0,:]]

      with open(Path+r"/"+'Feature33QueryImg152.txt', 'wb') as fp:
          pickle.dump(QueryImgFeature152, fp)

      with open(Path+r"/"+'Feature33QueryImg50.txt', 'wb') as fp:
        pickle.dump(QueryImgFeature50, fp)

      with open(Path+r"/"+'Feature33QueryImg18.txt', 'wb') as fp:
        pickle.dump(QueryImgFeature18, fp)

      with open(Path+r"/"+'Feature33TargetImg152.txt', 'wb') as fp:
        pickle.dump(TargetImgFeature152, fp)

      with open(Path+r"/"+'Feature33TargetImg50.txt', 'wb') as fp:
        pickle.dump(TargetImgFeature50, fp)

      with open(Path+r"/"+'Feature33TargetImg18.txt', 'wb') as fp:
        pickle.dump(TargetImgFeature18, fp)

     
################### Get Features of all images

def euclideandistance(signature,signatureimg):
    from scipy.spatial import distance
    return distance.euclidean(signature, signatureimg)

class FeaturesToFiles172():

  def __init__(self):
    super(FeaturesToFiles172, self).__init__()
    self.Path=Path1+r'/FeaturesToFiles172'
    self.train = datasets.Fashion200k(
        path=Path1,
        split='train',
        transform=torchvision.transforms.Compose([
            torchvision.transforms.Resize(224),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize([0.485, 0.456, 0.406],
                                              [0.229, 0.224, 0.225])
        ]))

  def SaveAllimgesToFile(self):    
    if(not os.path.isdir(self.Path)):
      os.makedirs(self.Path)

    with open(self.Path+r"/"+'FeaturesToFiles172.txt', 'wb') as fp:
      pickle.dump(self.train.imgs, fp)

    with open(self.Path+r"/"+'trainget_all_texts.txt', 'wb') as fp:
      pickle.dump(self.train.get_all_texts(), fp)
     
  def SaveAllFeatures(self):
    
    if(os.path.exists(self.Path+r"/"+'FeaturesToFiles172.txt') and os.path.exists(self.Path+r"/"+'trainget_all_texts.txt') ):
      print('172K Index File already found... begining of Extracting Features ')
    else:
      self.SaveAllimgesToFile()
      print('172K Index Files Created... begining of Extracting Features')

    with open (self.Path+r'/trainget_all_texts.txt', 'rb') as fp:
      alltexts = pickle.load(fp) 

    with open (self.Path+r'/FeaturesToFiles172.txt', 'rb') as fp:
      Idximgs = pickle.load(fp) 

    trig= img_text_composition_models.TIRG([t.encode().decode('utf-8') for t in alltexts],512)
    trig.load_state_dict(torch.load(Path1+r'\fashion200k.tirg.iter160k.pth' , map_location=torch.device('cpu') )['model_state_dict'])
    trig.eval()

    #print('First Extract Features using Tirg Model')
    #self.SaveimgTxtFToFileTirg(Idximgs,trig)
    #print('Extracting 152 50 18 Resnet')
    #self.SaveImgFeature1525018(Idximgs,trig)
    #self.SaveQueryStructFile(trig)
    self.SaveQueryStructFileِallFeatures(trig)
    
  def SaveimgTxtFToFileTirg(self,Idximgs,model):
    
    img=[]
    text_model=[]
    
    i=0
    for item in tqdm(Idximgs):      
      img += [model.extract_img_feature(torch.stack([self.train.get_img(i)]).float()).data.cpu().numpy()]
      text_model += [model.extract_text_feature([item['captions'][0]]).data.cpu().numpy()]
      i=i+1
    
    img=np.concatenate(img)
    text_model=np.concatenate(text_model)
    
    with open(self.Path+r"/"+'Features172imgTrig.txt', 'wb') as fp:
      pickle.dump(img, fp)

    with open(self.Path+r"/"+'Features172textTrig.txt', 'wb') as fp:
      pickle.dump(text_model, fp)
  
  def SaveImgFeature1525018(self,Idximgs,model):
    Resnet152 = models.resnet152(pretrained=True)
    Resnet152.fc = nn.Identity()
    Resnet152.eval()

    Resnet50 = models.resnet50(pretrained=True)
    Resnet50.fc = nn.Identity()
    Resnet50.eval()

    Resnet18 = models.resnet18(pretrained=True)
    Resnet18.fc = nn.Identity()
    Resnet18.eval()    

    i=0  
    Feature152=[]
    Feature50=[]
    Feature18=[]
    for item in tqdm(Idximgs):      
      
      
      img=self.train.get_img(i)
      img=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))
      i=i+1

      out=Resnet152(img)
      out = Variable(out, requires_grad=False)
      out=np.array(out)
      Feature152 +=[out[0,:]]

      out=Resnet50(img)
      out = Variable(out, requires_grad=False)
      out=np.array(out)
      Feature50 +=[out[0,:]]

      out=Resnet18(img)
      out = Variable(out, requires_grad=False)
      out=np.array(out)
      Feature18 +=[out[0,:]]

      
    with open(self.Path+r"/"+'Features172img152.txt', 'wb') as fp:
      pickle.dump(Feature152, fp)

    with open(self.Path+r"/"+'Features172img50.txt', 'wb') as fp:
      pickle.dump(Feature50, fp)

    with open(self.Path+r"/"+'Features172img18.txt', 'wb') as fp:
      pickle.dump(Feature18, fp)

  def ValidateFile(self,idx,model):
    

    with open (self.Path+r'/FeaturesToFiles172.txt', 'rb') as fp:
      Idximgs = pickle.load(fp) 

    print('Img in Index of Dataset:',self.train.imgs[idx])
    print('Img in Index from File:',Idximgs[idx])

    img = [model.extract_img_feature(torch.stack([self.train.get_img(idx)]).float()).data.cpu().numpy()]
    text_model = [model.extract_text_feature([self.train.imgs[idx]['captions'][0]]).data.cpu().numpy()]

    print('Caption=',self.train.imgs[idx]['captions'][0])

    with open (self.Path+r'/Features172imgTrig.txt', 'rb') as fp:
      trigimg = pickle.load(fp) 

    with open (self.Path+r'/Features172textTrig.txt', 'rb') as fp:
      trigtext = pickle.load(fp) 

    print ('Distance Between img Tirg:', euclideandistance(img,trigimg[idx]))
    print ('Distance Between text Tirg:', euclideandistance(text_model,trigtext[idx]))

    Resnet152 = models.resnet152(pretrained=True)
    Resnet152.fc = nn.Identity()
    Resnet152.eval()

    Resnet50 = models.resnet50(pretrained=True)
    Resnet50.fc = nn.Identity()
    Resnet50.eval()

    Resnet18 = models.resnet18(pretrained=True)
    Resnet18.fc = nn.Identity()
    Resnet18.eval()    

    
    img=self.train.get_img(idx)
    img=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))
    

    out=Resnet152(img)
    out = Variable(out, requires_grad=False)
    out=np.array(out)
    Feature152 =[out[0,:]]

    out=Resnet50(img)
    out = Variable(out, requires_grad=False)
    out=np.array(out)
    Feature50 =[out[0,:]]

    out=Resnet18(img)
    out = Variable(out, requires_grad=False)
    out=np.array(out)
    Feature18 =[out[0,:]]

    with open (self.Path+r'/Features172img152.txt', 'rb') as fp:
      img152 = pickle.load(fp) 
    
    with open (self.Path+r'/Features172img50.txt', 'rb') as fp:
      img50 = pickle.load(fp) 

    with open (self.Path+r'/Features172img18.txt', 'rb') as fp:
      img18 = pickle.load(fp) 

    print ('Distance Between img 18:', euclideandistance(Feature18,img18[idx]))
    print ('Distance Between img 50:', euclideandistance(Feature50,img50[idx]))
    print ('Distance Between img 152:', euclideandistance(Feature152,img152[idx]))

  def SaveQueryStructFile(self,model):
    QueryInfo=[]
    for i in range(172048):#172048
      print('Extracting Feature From image=',i,end='\r')  
      item = self.train[i]
      idx = {
          'QueryID': item['source_img_id'],
          'TargetID':item['target_img_id'],
          'Mod':  item['mod']['str'],
          'QueryCaption':item['source_caption'],
          'TargetCaption':item['target_caption'],
          'QueryURL':item['source_path'],
          'TargetURL':item['target_path'],
          'ModF':model.extract_text_feature([item['mod']['str']]).data.cpu().numpy()
      }
      QueryInfo += [idx]
    
    with open(self.Path+r"/"+'Features172QueryStructure.txt', 'wb') as fp:
      pickle.dump(QueryInfo, fp)

  def SaveQueryStructFileِallFeatures(self,model):
    with open (self.Path+r'/Features172QueryStructure.txt', 'rb') as fp:
      QueryInfoold = pickle.load(fp) 

    with open (self.Path+r'/Features172imgTrig.txt', 'rb') as fp:
      trigimg = pickle.load(fp) 

    with open (self.Path+r'/Features172textTrig.txt', 'rb') as fp:
      trigtext = pickle.load(fp) 

    with open (self.Path+r'/Features172img152.txt', 'rb') as fp:
      img152 = pickle.load(fp) 
    
    with open (self.Path+r'/Features172img50.txt', 'rb') as fp:
      img50 = pickle.load(fp) 

    with open (self.Path+r'/Features172img18.txt', 'rb') as fp:
      img18 = pickle.load(fp) 


    QueryInfo=[]
    for i in range(172048):#172048
      print('Extracting Feature From image=',i,end='\r')  
      item = QueryInfoold[i]
      idx = {
          'QueryID': item['QueryID'],
          'TargetID':item['TargetID'],
          'Mod':  item['Mod'],
          'QueryCaption':item['QueryCaption'],
          'TargetCaption':item['TargetCaption'],
          'QueryURL':item['QueryURL'],
          'TargetURL':item['TargetURL'],
          'ModF':item['ModF'],
          'QueryCaptionF':trigtext[item['QueryID']],
          'TargetCaptionF':trigtext[item['TargetID']],
          'Query18F':img18[item['QueryID']],
          'Query50F':img50[item['QueryID']],
          'Query152F':img152[item['QueryID']],
          'QuerytrigF':trigimg[item['QueryID']],
          'Target18F':img18[item['TargetID']],
          'Target50F':img50[item['TargetID']],
          'Target152F':img152[item['TargetID']],
          'targettirgF':trigimg[item['TargetID']]

      }
      QueryInfo += [idx]
    
    with open(self.Path+r"/"+'Features172QueryStructureallF.txt', 'wb') as fp:
      pickle.dump(QueryInfo, fp)


class FeaturesToFiles33():

  def __init__(self):
    super(FeaturesToFiles33, self).__init__()
    self.Path=Path1+r'/FeaturesToFiles33'
    self.test = datasets.Fashion200k(
        path=Path1,
        split='test',
        transform=torchvision.transforms.Compose([
            torchvision.transforms.Resize(224),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize([0.485, 0.456, 0.406],
                                              [0.229, 0.224, 0.225])
        ]))

  def SaveAllimgesToFile(self):    
    if(not os.path.isdir(self.Path)):
      os.makedirs(self.Path)

    with open(self.Path+r"/"+'FeaturesToFiles33.txt', 'wb') as fp:
      pickle.dump(self.test.imgs, fp)
     
  def SaveAllFeatures(self):
    
    if(os.path.exists(self.Path+r"/"+'FeaturesToFiles172.txt') and os.path.exists(datasets.FeaturesToFiles172().Path+r"/"+'trainget_all_texts.txt') ):
      print('172K Index File already found... begining of Extracting Features ')
    else:
      self.SaveAllimgesToFile()
      print('172K Index Files Created... begining of Extracting Features')

    with open (datasets.FeaturesToFiles172().Path+r'/trainget_all_texts.txt', 'rb') as fp:
      alltexts = pickle.load(fp) 

    with open (self.Path+r'/FeaturesToFiles33.txt', 'rb') as fp:
      Idximgs = pickle.load(fp) 

    trig= img_text_composition_models.TIRG([t.encode().decode('utf-8') for t in alltexts],512)
    trig.load_state_dict(torch.load(Path1+r'\fashion200k.tirg.iter160k.pth' , map_location=torch.device('cpu') )['model_state_dict'])
    trig.eval()

    #print('First Extract Features using Tirg Model')
    #self.SaveimgTxtFToFileTirg(Idximgs,trig)
    #print('Extracting 152 50 18 Resnet')
    #self.SaveImgFeature1525018(Idximgs,trig)
    #self.SaveQueryStructFile(trig)
    self.SaveQueryStructFileِallFeatures(trig)
    
  def SaveimgTxtFToFileTirg(self,Idximgs,model):
    
    img=[]
    text_model=[]

    i=0  
    for item in tqdm(Idximgs):      
      img += [model.extract_img_feature(torch.stack([self.test.get_img(i)]).float()).data.cpu().numpy()]
      text_model += [model.extract_text_feature([item['captions'][0]]).data.cpu().numpy()]
      i=i+1
    
    img=np.concatenate(img)
    text_model=np.concatenate(text_model)
    
    with open(self.Path+r"/"+'Features33imgTrig.txt', 'wb') as fp:
      pickle.dump(img, fp)

    with open(self.Path+r"/"+'Features33textTrig.txt', 'wb') as fp:
      pickle.dump(text_model, fp)
  
  def SaveImgFeature1525018(self,Idximgs,model):
    Resnet152 = models.resnet152(pretrained=True)
    Resnet152.fc = nn.Identity()
    Resnet152.eval()

    Resnet50 = models.resnet50(pretrained=True)
    Resnet50.fc = nn.Identity()
    Resnet50.eval()

    Resnet18 = models.resnet18(pretrained=True)
    Resnet18.fc = nn.Identity()
    Resnet18.eval()    
    i=0
    Feature152=[]
    Feature50=[]
    Feature18=[]
    for item in tqdm(Idximgs):      
      
      
      img=self.test.get_img(i)
      img=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))
      i=i+1

      out=Resnet152(img)
      out = Variable(out, requires_grad=False)
      out=np.array(out)
      Feature152 +=[out[0,:]]

      out=Resnet50(img)
      out = Variable(out, requires_grad=False)
      out=np.array(out)
      Feature50 +=[out[0,:]]

      out=Resnet18(img)
      out = Variable(out, requires_grad=False)
      out=np.array(out)
      Feature18 +=[out[0,:]]

      
    with open(self.Path+r"/"+'Features33img152.txt', 'wb') as fp:
      pickle.dump(Feature152, fp)

    with open(self.Path+r"/"+'Features33img50.txt', 'wb') as fp:
      pickle.dump(Feature50, fp)

    with open(self.Path+r"/"+'Features33img18.txt', 'wb') as fp:
      pickle.dump(Feature18, fp)

  def ValidateFile(self,idx,model):
    
    with open (self.Path+r'/FeaturesToFiles33.txt', 'rb') as fp:
      Idximgs = pickle.load(fp) 

    print('Img in Index of Dataset:',self.test.imgs[idx])
    print('Img in Index from File:',Idximgs[idx])

    img = [model.extract_img_feature(torch.stack([self.test.get_img(idx)]).float()).data.cpu().numpy()]
    text_model = [model.extract_text_feature([self.test.imgs[idx]['captions'][0]]).data.cpu().numpy()]

    print('Caption=',self.test.imgs[idx]['captions'][0])

    with open (self.Path+r'/Features33imgTrig.txt', 'rb') as fp:
      trigimg = pickle.load(fp) 

    with open (self.Path+r'/Features33textTrig.txt', 'rb') as fp:
      trigtext = pickle.load(fp) 

    print ('Distance Between img Tirg:', euclideandistance(img,trigimg[idx]))
    print ('Distance Between text Tirg:', euclideandistance(text_model,trigtext[idx]))

    Resnet152 = models.resnet152(pretrained=True)
    Resnet152.fc = nn.Identity()
    Resnet152.eval()

    Resnet50 = models.resnet50(pretrained=True)
    Resnet50.fc = nn.Identity()
    Resnet50.eval()

    Resnet18 = models.resnet18(pretrained=True)
    Resnet18.fc = nn.Identity()
    Resnet18.eval()    

    
    img=self.test.get_img(idx)
    img=torch.reshape(img,(1,img.shape[0],img.shape[1],img.shape[2]))
    

    out=Resnet152(img)
    out = Variable(out, requires_grad=False)
    out=np.array(out)
    Feature152 =[out[0,:]]

    out=Resnet50(img)
    out = Variable(out, requires_grad=False)
    out=np.array(out)
    Feature50 =[out[0,:]]

    out=Resnet18(img)
    out = Variable(out, requires_grad=False)
    out=np.array(out)
    Feature18 =[out[0,:]]

    with open (self.Path+r'/Features33img152.txt', 'rb') as fp:
      img152 = pickle.load(fp) 
    
    with open (self.Path+r'/Features33img50.txt', 'rb') as fp:
      img50 = pickle.load(fp) 

    with open (self.Path+r'/Features33img18.txt', 'rb') as fp:
      img18 = pickle.load(fp) 

    print ('Distance Between img 18:', euclideandistance(Feature18,img18[idx]))
    print ('Distance Between img 50:', euclideandistance(Feature50,img50[idx]))
    print ('Distance Between img 152:', euclideandistance(Feature152,img152[idx]))

  def SaveQueryStructFile(self,model):
    QueryInfo=[]
    test_queries = self.test .get_test_queries()
    for item in tqdm(test_queries):
       
      idx = {
          'QueryID': item['source_img_id'],
          'TargetID':item['target_id'],
          'Mod':  item['mod']['str'],
          'QueryCaption':item['source_caption'],
          'TargetCaption':item['target_caption'],
          'QueryURL':item['source_path'],
          'TargetURL':item['target_path'],
          'ModF':model.extract_text_feature([item['mod']['str']]).data.cpu().numpy()
      }
      QueryInfo += [idx]
    
    with open(self.Path+r"/"+'Features33QueryStructure.txt', 'wb') as fp:
      pickle.dump(QueryInfo, fp)

  def SaveQueryStructFileِallFeatures(self,model):
    with open (self.Path+r'/Features33QueryStructure.txt', 'rb') as fp:
      QueryInfoold = pickle.load(fp) 

    with open (self.Path+r'/Features33imgTrig.txt', 'rb') as fp:
      trigimg = pickle.load(fp) 

    with open (self.Path+r'/Features33textTrig.txt', 'rb') as fp:
      trigtext = pickle.load(fp) 

    with open (self.Path+r'/Features33img152.txt', 'rb') as fp:
      img152 = pickle.load(fp) 
    
    with open (self.Path+r'/Features33img50.txt', 'rb') as fp:
      img50 = pickle.load(fp) 

    with open (self.Path+r'/Features33img18.txt', 'rb') as fp:
      img18 = pickle.load(fp) 


    QueryInfo=[]
    for i in range(len(QueryInfoold)):
      print('Extracting Feature From image=',i,end='\r')  
      item = QueryInfoold[i]
      idx = {
          'QueryID': item['QueryID'],
          'TargetID':item['TargetID'],
          'Mod':  item['Mod'],
          'QueryCaption':item['QueryCaption'],
          'TargetCaption':item['TargetCaption'],
          'QueryURL':item['QueryURL'],
          'TargetURL':item['TargetURL'],
          'ModF':item['ModF'],
          'QueryCaptionF':trigtext[item['QueryID']],
          'TargetCaptionF':trigtext[item['TargetID']],
          'Query18F':img18[item['QueryID']],
          'Query50F':img50[item['QueryID']],
          'Query152F':img152[item['QueryID']],
          'QuerytrigF':trigimg[item['QueryID']],
          'Target18F':img18[item['TargetID']],
          'Target50F':img50[item['TargetID']],
          'Target152F':img152[item['TargetID']],
          'targettirgF':trigimg[item['TargetID']]

      }
      QueryInfo += [idx]
    
    with open(self.Path+r"/"+'Features33QueryStructureallF.txt', 'wb') as fp:
      pickle.dump(QueryInfo, fp)

  
