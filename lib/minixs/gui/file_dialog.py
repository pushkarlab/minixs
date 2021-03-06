import wx
import os

def FileDialog(parent, dirlist, type, title, wildcard='', save=False, multiple=False):
  """
  Show a file dialog and return selected path(s)
  """
  if type not in dirlist.keys() or not dirlist[type]:
    dirlist[type] = dirlist['last']

  style = 0
  if save:
    style |= wx.FD_SAVE
  else:
    style |= wx.FD_OPEN
  if multiple:
    style |= wx.FD_MULTIPLE

  dlg = wx.FileDialog(parent, title,
      dirlist[type],
      wildcard=wildcard,
      style=style)

  ret = dlg.ShowModal()

  paths = []
  if ret == wx.ID_OK:
    paths = dlg.GetPaths()
    paths.sort()
    if (paths):
      directory = os.path.dirname(paths[0])
    else:
      directory = dlg.GetDirectory()
    dirlist[type] = dirlist['last'] = directory

  dlg.Destroy()

  if not paths:
    return None

  if multiple:
    return paths
  else:
    return paths[0]

