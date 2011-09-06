from minixs.progress import ProgressIndicator
import wx

class WxProgressIndicator(ProgressIndicator):
  def __init__(self, name, title):
    ProgressIndicator.__init__(self, name)

    self.dialog = wx.ProgressDialog(title, name, maximum=100, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
    self.dialog.Show()

  def do_update(self):
    self.dialog.Update(int(self.progress * 100), self.msg)
