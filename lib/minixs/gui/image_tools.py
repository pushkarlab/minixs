import wx
import wx.lib.newevent
from numpy import sqrt

from mouse_event import *

EventRangeActionChanged, EVT_RANGE_ACTION_CHANGED = wx.lib.newevent.NewCommandEvent()
EventRangeChanged, EVT_RANGE_CHANGED = wx.lib.newevent.NewCommandEvent()

KILLZONE_COLORS = {
    'fill': wx.Colour(200,0,0,200),
    'active_fill': wx.Colour(255, 150, 150, 200),
    'place_fill': wx.Colour(200, 200, 200, 200),
    'stroke': wx.Colour(255, 255, 255, 255),
    'active_stroke': wx.Colour(255, 255, 255, 255),
    'resize_stroke': wx.Colour(34, 255, 255, 255),
    'move_stroke': wx.Colour(255, 255, 255, 255),
    'place_stroke': wx.Colour(255, 255, 255, 255),
    }

class Tool(object):
  def __init__(self, parent):
    self.parent = parent
    self.parent.AddTool(self)

    self.active = False
    self.visible = True

  def SetActive(self, active):
    self.active = active

  def SetVisible(self, visible):
    if visible == self.visible:
      return

    self.visible = visible
    self.parent.Refresh()

  def OnLeftDown(self, evt):
    pass

  def OnLeftUp(self, evt):
    pass

  def OnRightDown(self, evt):
    pass

  def OnRightUp(self, evt):
    pass

  def OnMiddleDown(self, evt):
    pass

  def OnMiddleUp(self, evt):
    pass

  def OnMotion(self, evt):
    pass

  def OnEnterWindow(self, evt):
    pass

  def OnLeaveWindow(self, evt):
    pass

  def OnPaint(self, evt, dc):
    pass

class RangeTool(Tool):
  """
  A tool to allow selecting one or more ranges in one or more directions
  """
  VERTICAL = 1
  HORIZONTAL = 2

  ACTION_NONE = 0
  ACTION_RESIZE_L = 0x01
  ACTION_RESIZE_R = 0x02
  ACTION_RESIZE_T = 0x04
  ACTION_RESIZE_B = 0x08
  ACTION_MOVE     = 0x10
  ACTION_PROPOSED = 0x100

  ACTION_RESIZE_TL = ACTION_RESIZE_T | ACTION_RESIZE_L
  ACTION_RESIZE_TR = ACTION_RESIZE_T | ACTION_RESIZE_R
  ACTION_RESIZE_BL = ACTION_RESIZE_B | ACTION_RESIZE_L
  ACTION_RESIZE_BR = ACTION_RESIZE_B | ACTION_RESIZE_R

  ACTION_RESIZE = ACTION_RESIZE_L | ACTION_RESIZE_R | \
                  ACTION_RESIZE_T | ACTION_RESIZE_B

  def __init__(self, *args, **kwargs):
    """
    Initialize tool
    """
    Tool.__init__(self, *args, **kwargs)

    self.rects = []
    self.active_rect = None

    self.multiple = False
    self.direction = self.VERTICAL | self.HORIZONTAL

    self.action = self.ACTION_NONE

    self.brush = wx.Brush(wx.Colour(255,255,255,50))
    self.pen = wx.Pen('#ffff22', 1, wx.DOT_DASH)
    self.active_pen = wx.Pen('#33dd33', 1, wx.DOT_DASH)
    self.action_pen = wx.Pen('#22ffff', 2, wx.SOLID)

    self.range_changed = False
    self.post_range_change_immediate = False

  def RangeChanged(self):
    if self.post_range_change_immediate:
      self.PostEventRangeChanged()
    else:
      self.range_changed = True

  def PostEventRangeChanged(self):
    """
    Send event indicating that selected range has changed
    """
    evt = EventRangeChanged(self.parent.Id, range=self.rects)
    wx.PostEvent(self.parent, evt)

  def PostEventRangeActionChanged(self, in_window):
    """
    Send event indicating that current action has changed
    """
    evt = EventRangeActionChanged(self.parent.Id,
        action=self.action,
        range=self.active_rect,
        in_window=in_window)
    wx.PostEvent(self.parent, evt)

  def DetermineAction(self, x, y):
    """
    Determine action to perform based on the provided location

    Parameters
    ----------
      x: x coordinate
      y: y coordinate

    Returns
    -------
      (rect, action)

      rect: the rectangle to act on
      action: the action to perform (a bitmask of self.ACTION_*)
    """

    off = 4
    action = self.ACTION_NONE
    active_rect = None

    # run through rects backwards (newest are on top)
    for rect in self.rects[::-1]:
      (x1,y1),(x2,y2) = rect

      # check if within offset of a rect edge, if so, resize
      if y1 - off < y < y2 + off:
        if abs(x1 - x) < off:
          action |= self.ACTION_RESIZE_L
          active_rect = rect
        elif abs(x2 - x) < off:
          action |= self.ACTION_RESIZE_R
      if x1 - off < x < x2 + off:
        if abs(y1 - y) < off:
          action |= self.ACTION_RESIZE_T
        elif abs(y2 - y) < off:
          action |= self.ACTION_RESIZE_B

      # not close to edge, but within rect => move
      if action == self.ACTION_NONE:
        if x1 < x < x2 and y1 < y < y2:
          action = self.ACTION_MOVE

      # only perform actions commensurate with direction
      mask = self.ACTION_MOVE
      if self.direction & self.VERTICAL:
        mask |= self.ACTION_RESIZE_T
        mask |= self.ACTION_RESIZE_B
      if self.direction & self.HORIZONTAL:
        mask |= self.ACTION_RESIZE_L
        mask |= self.ACTION_RESIZE_R
      action &= mask

      if action != self.ACTION_NONE:
        return (rect, action)

    return (None, self.ACTION_NONE)

  def SetMultiple(self, multiple):
    self.multiple = multiple

  def SetDirection(self, direction):
    self.direction = direction
    self.parent.Refresh()

  def ToggleDirection(self, direction, on=None):
    """
    Toggle range direction

    Parameters
    ----------
      direction: Crosshair.VERTICAL or .HORIZONTAL
      on: True for on, False for off, or None for toggle 

    Note: the directions can be bitwise or'd together. (e.g. RangeTool.VERTICAL | RangeTool.HORIZONTAL)
    """

    if on is None:
      self.direction ^= direction
    elif on:
      self.direction |= direction
    else:
      self.direction &= ~direction

  def OnLeftDown(self, evt):
    """
    Handle left mouse down
    """

    if mouse_event_modifier_mask(evt) != MOD_NONE:
      return

    x, y = evt.GetPosition()
    x, y = self.parent.CoordScreenToBitmap(x,y)

    w, h = self.parent.GetBitmapSize()

    if self.action & self.ACTION_PROPOSED:
      self.action &= ~self.ACTION_PROPOSED
      self.action_start = (x,y)
    else:
      if self.direction & self.VERTICAL:
        y1 = y
        y2 = y + 1
      else:
        y1 = 0
        y2 = h
      if self.direction & self.HORIZONTAL:
        x1 = x
        x2 = x + 1
      else:
        x1 = 0
        x2 = w

      rect = [[x1,y1],[x2,y2]]
      if self.multiple:
        self.rects.append(rect)
      else:
        self.rects = [rect]

      self.active_rect = rect
      self.action = self.ACTION_NONE
      if self.direction & self.HORIZONTAL:
        self.action |= self.ACTION_RESIZE_R
      if self.direction & self.VERTICAL:
        self.action |= self.ACTION_RESIZE_B

    self.parent.Refresh()

  def OnLeftUp(self, evt):
    """
    Handle left mouse up
    """

    if mouse_event_modifier_mask(evt) != MOD_NONE:

      # not all computers (Macs) have middle mouse buttons, so let
      # shift-left-click
      if evt.ShiftDown():
        self.SplitActiveRect(evt.ControlDown())
      return

    x,y = evt.GetPosition()
    x,y = self.parent.CoordScreenToBitmap(x,y)
    (x1,y1), (x2,y2) = self.active_rect

    if self.action & self.ACTION_RESIZE:
      # normalize rect coords so x1<x2 and y1<y2
      if x2 < x1:
        self.active_rect[0][0], self.active_rect[1][0] = x2, x1
      if y2 < y1:
        self.active_rect[0][1], self.active_rect[1][1] = y2, y1

      # don't keep rects with vanishing size
      if abs(x2 - x1) < 2 or abs(y2 - y1) < 2:
        self.rects.remove(self.active_rect)
        self.parent.Refresh()

    rect, action = self.DetermineAction(x, y)
    if action != self.ACTION_NONE:
      action |= self.ACTION_PROPOSED
    self.active_rect = rect
    self.action = action 

    if self.range_changed:
      self.PostEventRangeChanged()
      self.range_changed = False

    self.parent.Refresh()

  def OnRightUp(self, evt):
    """
    Handle right mouse up
    """

    if mouse_event_modifier_mask(evt) != MOD_NONE:
      return

    if self.action & self.ACTION_PROPOSED:
      self.rects.remove(self.active_rect)
      self.active_rect = None
      self.action = self.ACTION_NONE
      self.PostEventRangeChanged()
      self.parent.Refresh()

  def OnMiddleUp(self, evt):
    """
    Handle middle mouse up
    """

    horizontal = evt.ControlDown()
    self.SplitActiveRect(horizontal)


  def SplitActiveRect(self, horizontal=False):
    """
    Split active rectangle in half.

    Parameters:
      horizontal: if True, split rect horizontally. else, split rect vertically
    """

    if self.action & self.ACTION_PROPOSED:
      r = self.active_rect
      (x1,y1), (x2,y2) = r
      r2 = [[x1,y1],[x2,y2]]

      # split active rect in half
      if horizontal:
        #split horizontally
        (x1,y1), (x2,y2) = r
        yp = (y1 + y2) / 2.0
        r[1][1] = yp-1
        r2[0][1] = yp+1
      else:
        #split vertically
        xp = (x1 + x2) / 2.0
        r[1][0] = xp-2
        r2[0][0] = xp+2

      self.rects.append(r2)
      self.PostEventRangeChanged()
      self.parent.Refresh()

  def OnMotion(self, evt):
    """
    Handle mouse motion
    """
    x, y = evt.GetPosition()
    x, y = self.parent.CoordScreenToBitmap(x,y)

    w, h = self.parent.GetBitmapSize()

    # not currently performing an action
    if self.action == self.ACTION_NONE or self.action & self.ACTION_PROPOSED:
      rect, action = self.DetermineAction(x,y)

      needs_refresh = False
      if self.action & ~self.ACTION_PROPOSED != action or rect != self.active_rect:
        needs_refresh = True

      if rect:
        action |= self.ACTION_PROPOSED

      if action != self.action or rect != self.active_rect or rect is None:
        self.action = action
        self.active_rect = rect

        self.PostEventRangeActionChanged(in_window=True)

      if needs_refresh:
        self.parent.Refresh()

    elif self.action & self.ACTION_RESIZE:
      # clamp mouse to within panel
      if x < 0: x = 0
      if x > w: x = w
      if y < 0: y = 0
      if y > h: y = h

      if self.action & self.ACTION_RESIZE_L:
        self.active_rect[0][0] = x
      elif self.action & self.ACTION_RESIZE_R:
        self.active_rect[1][0] = x
      if self.action & self.ACTION_RESIZE_T:
        self.active_rect[0][1] = y
      elif self.action & self.ACTION_RESIZE_B:
        self.active_rect[1][1] = y

      self.RangeChanged()
      self.parent.Refresh()

    elif self.action & self.ACTION_MOVE:
      (x1, y1), (x2, y2) = self.active_rect
      xs,ys = self.action_start
      dx, dy = x - xs, y - ys

      if dx < -x1: dx = -x1
      if dy < -y1: dy = -y1
      if dx > w-x2: dx = w-x2
      if dy > h-y2: dy = h-y2

      if self.direction & self.HORIZONTAL:
        self.active_rect[0][0] += dx
        self.active_rect[1][0] += dx
      if self.direction & self.VERTICAL:
        self.active_rect[0][1] += dy
        self.active_rect[1][1] += dy
      self.action_start = (x,y)

      self.RangeChanged()
      self.parent.Refresh()

  def OnEnterWindow(self, evt):
    """
    Handle entering window
    """
    pass

  def OnLeaveWindow(self, evt):
    """
    Handle leaving window
    """
    if self.action & self.ACTION_PROPOSED or self.action == self.ACTION_NONE:
      self.action = self.ACTION_NONE
      self.active_rect = None

      self.PostEventRangeActionChanged(in_window=False)
      self.parent.Refresh()

  def OnPaint(self, evt, dc):
    """
    Draw tool
    """
    gcdc = wx.GCDC(dc)

    dc.SetBrush(wx.TRANSPARENT_BRUSH)
    gcdc.SetBrush(self.brush)
    gcdc.SetPen(wx.TRANSPARENT_PEN)

    for r in self.rects:
      if r == self.active_rect:
        dc.SetPen(self.active_pen)
      else:
        dc.SetPen(self.pen)

      (x1,y1),(x2,y2) = r 

      # transform coords
      x1,y1 = self.parent.CoordBitmapToScreen(x1,y1)
      x2,y2 = self.parent.CoordBitmapToScreen(x2,y2)

      gcdc.DrawRectangle(x1,y1,x2-x1,y2-y1)
      dc.DrawRectangle(x1,y1,x2-x1+1,y2-y1+1)

      if self.active_rect and self.action & self.ACTION_RESIZE and self.action & self.ACTION_PROPOSED:

        dc.SetPen(self.action_pen)
        (x1,y1),(x2,y2) = self.active_rect
        x1,y1 = self.parent.CoordBitmapToScreen(x1,y1)
        x2,y2 = self.parent.CoordBitmapToScreen(x2,y2)

        if self.action & self.ACTION_RESIZE_L:
          dc.DrawLine(x1,y1,x1,y2)
        if self.action & self.ACTION_RESIZE_R:
          dc.DrawLine(x2,y1,x2,y2)
        if self.action & self.ACTION_RESIZE_T:
          dc.DrawLine(x1,y1,x2,y1)
        if self.action & self.ACTION_RESIZE_B:
          dc.DrawLine(x1,y2,x2,y2)


class Crosshair(Tool):
  VERTICAL = 1
  HORIZONTAL = 2

  def __init__(self, *args, **kwargs):
    Tool.__init__(self, *args, **kwargs)

    self.direction = self.VERTICAL | self.HORIZONTAL
    self.pos = None

    self.pen = wx.Pen('#222222', 1, wx.SOLID)

  def SetDirection(self, direction):
    self.direction = direction
    self.parent.Refresh()

  def ToggleDirection(self, direction, on=None):
    """
    Toggle crosshair direction

    Parameters
    ----------
      direction: Crosshair.VERTICAL or .HORIZONTAL
      on: True for on, False for off, or None for toggle 

    Note: the directions can be bitwise or'd together. (e.g. Crosshair.VERTICAL | Crosshair.HORIZONTAL)
    """

    if on is None:
      self.direction ^= direction
    elif on:
      self.direction |= direction
    else:
      self.direction &= ~direction

  def OnLeftDown(self, evt):
    pass

  def OnMotion(self, evt):
    self.pos = evt.GetPosition()
    self.parent.Refresh()

  def OnLeaveWindow(self, evt):
    self.pos = None
    self.parent.Refresh()

  def OnPaint(self, evt, dc):
    if self.pos is None:
      return

    dc.SetLogicalFunction(wx.INVERT)

    w, h = self.parent.GetSize()
    dc.SetPen(self.pen)

    if self.direction & self.VERTICAL:
      x1 = x2 = self.pos[0]
      y1 = 0
      y2 = h
      dc.DrawLine(x1,y1,x2,y2)

    if self.direction & self.HORIZONTAL:
      y1 = y2 = self.pos[1]
      x1 = 0
      x2 = w
      dc.DrawLine(x1,y1,x2,y2)

    dc.SetLogicalFunction(wx.COPY)




class CircleTool(Tool):
  """
  A tool to allow selecting one or more circular regions
  """
  ACTION_NONE = 0
  ACTION_RESIZE = 0x01
  ACTION_MOVE     = 0x02
  ACTION_PROPOSED = 0x100

  def __init__(self, *args, **kwargs):
    """
    Initialize tool
    """
    Tool.__init__(self, *args, **kwargs)

    self.circles = []
    self.active_circle = None

    self.multiple = True

    self.action = self.ACTION_NONE

    self.colors = {
        'fill': wx.Colour(200,0,0,200),
        'active_fill': wx.Colour(255, 150, 150, 200),
        'place_fill': wx.Colour(200, 200, 200, 200),
        'stroke': wx.Colour(255, 255, 255, 255),
        'active_stroke': wx.Colour(255, 255, 255, 255),
        'resize_stroke': wx.Colour(34, 255, 255, 255),
        'move_stroke': wx.Colour(255, 255, 255, 255),
        'place_stroke': wx.Colour(255, 255, 255, 255),
        }

    self.UpdateColors()

    self.coords = None

    self.range_changed = False
    self.post_range_change_immediate = False

    self.radius = 6

  def UpdateColors(self):
    self.brush = wx.Brush(self.colors['fill'])
    self.active_brush = wx.Brush(self.colors['active_fill'])
    self.place_brush = wx.Brush(self.colors['place_fill'])

    self.pen = wx.Pen(self.colors['stroke'], 1, wx.SOLID)
    self.active_pen = wx.Pen(self.colors['active_stroke'], 1, wx.SOLID)
    self.resize_pen = wx.Pen(self.colors['resize_stroke'], 2, wx.SOLID)
    self.move_pen = wx.Pen(self.colors['move_stroke'], 2, wx.SOLID)
    self.place_pen = wx.Pen(self.colors['place_stroke'], 2, wx.SOLID)


  def RangeChanged(self):
    if self.post_range_change_immediate:
      self.PostEventRangeChanged()
    else:
      self.range_changed = True

  def PostEventRangeChanged(self):
    """
    Send event indicating that selected range has changed
    """
    evt = EventRangeChanged(self.parent.Id, range=self.circles)
    wx.PostEvent(self.parent, evt)

  def PostEventRangeActionChanged(self, in_window):
    """
    Send event indicating that current action has changed
    """
    evt = EventRangeActionChanged(self.parent.Id,
        action=self.action,
        range=self.active_circle,
        in_window=in_window)
    wx.PostEvent(self.parent, evt)

  def DetermineAction(self, x, y):
    """
    Determine action to perform based on the provided location

    Parameters
    ----------
      x: x coordinate
      y: y coordinate

    Returns
    -------
      (circle, action)

      circle: the circle to act on
      action: the action to perform (a bitmask of self.ACTION_*)
    """

    scale = self.parent.zoom
    if scale < 0: scale = -1.0/scale
    off = 5.0 / scale
    #off = 4.0

    action = self.ACTION_NONE
    active_circle = None
   
    # run through circles backwards (newest are on top)
    for circle in self.circles[::-1]:
      xc, yc, r = circle

      d = sqrt((x-xc)**2 + (y-yc)**2)

      # if within circle, move it
      if d < r:
        action = self.ACTION_MOVE
        active_circle = circle

      # if outside of circle, but close, resize it
      elif d < r+off:
        action = self.ACTION_RESIZE
        active_circle = circle

      if action != self.ACTION_NONE:
        return (circle, action)

    return (None, self.ACTION_NONE)

  def SetMultiple(self, multiple):
    self.multiple = multiple

  def OnLeftDown(self, evt):
    """
    Handle left mouse down
    """

    if mouse_event_modifier_mask(evt) != MOD_NONE:
      return

    x, y = evt.GetPosition()
    x, y = self.parent.CoordScreenToBitmap(x,y)

    w, h = self.parent.GetBitmapSize()

    if self.action & self.ACTION_PROPOSED:
      # perform an action on exisiting circle
      self.action &= ~self.ACTION_PROPOSED
      self.action_start = (x,y)
    else:
      # create a new circle
      circle = [x,y,self.radius]
      if self.multiple:
        self.circles.append(circle)
      else:
        self.circles = [circle]

      self.active_circle = circle 
      self.action = self.ACTION_MOVE
      self.action_start = (x,y)

    self.parent.Refresh()

  def OnLeftUp(self, evt):
    """
    Handle left mouse up
    """

    if mouse_event_modifier_mask(evt) != MOD_NONE:

      # not all computers (Macs) have middle mouse buttons, so let
      # shift-left-click
      if evt.ShiftDown():
        self.SplitActiveRect(evt.ControlDown())
      return

    x,y = evt.GetPosition()
    x,y = self.parent.CoordScreenToBitmap(x,y)

    if self.action == self.ACTION_RESIZE and self.active_circle[2] < 1:
      self.circles.remove(self.active_circle)
      self.active_circle = None

    circle, action = self.DetermineAction(x, y)
    if action != self.ACTION_NONE:
      action |= self.ACTION_PROPOSED
    self.active_circle = circle
    self.action = action 

    if self.range_changed:
      self.PostEventRangeChanged()
      self.range_changed = False

    self.parent.Refresh()

  def OnRightUp(self, evt):
    """
    Handle right mouse up
    """

    if mouse_event_modifier_mask(evt) != MOD_NONE:
      return

    if self.action & self.ACTION_PROPOSED:
      self.circles.remove(self.active_circle)
      self.active_circle = None
      self.action = self.ACTION_NONE
      self.PostEventRangeChanged()
      self.parent.Refresh()

  def OnMotion(self, evt):
    """
    Handle mouse motion
    """
    x, y = evt.GetPosition()
    x, y = self.parent.CoordScreenToBitmap(x,y)

    w, h = self.parent.GetBitmapSize()

    # store current coords to show where new circle will be placed
    self.coords = (x,y)

    # not currently performing an action
    if self.action == self.ACTION_NONE or self.action & self.ACTION_PROPOSED:
      circle, action = self.DetermineAction(x,y)

      if circle:
        action |= self.ACTION_PROPOSED

      if action != self.action or circle != self.active_circle or circle is None:
        self.action = action
        self.active_circle = circle

        self.PostEventRangeActionChanged(in_window=True)

    elif self.action & self.ACTION_RESIZE:
      xc,yc = self.active_circle[0:2]
      radius = int(sqrt((x-xc)**2 + (y-yc)**2))
      if radius < 2: radius = 2
      self.active_circle[2] = radius
      self.RangeChanged()

    elif self.action & self.ACTION_MOVE:
      xs,ys = self.action_start
      dx, dy = x - xs, y - ys

      self.active_circle[0:2] = (xs+dx,ys+dy)
      self.action_start = (x,y)

      self.RangeChanged()
    self.parent.Refresh()

  def OnEnterWindow(self, evt):
    """
    Handle entering window
    """
    pass

  def OnLeaveWindow(self, evt):
    """
    Handle leaving window
    """
    self.coords = None

    if self.action & self.ACTION_PROPOSED or self.action == self.ACTION_NONE:
      self.action = self.ACTION_NONE
      self.active_circle = None

      self.PostEventRangeActionChanged(in_window=False)
      self.parent.Refresh()

  def OnPaint(self, evt, dc):
    """
    Draw tool
    """
    gcdc = wx.GCDC(dc)

    dc.SetBrush(wx.TRANSPARENT_BRUSH)
    gcdc.SetBrush(self.brush)
    gcdc.SetPen(wx.TRANSPARENT_PEN)

    scale = self.parent.zoom
    if scale < 0: scale = -1.0/scale

    for c in self.circles:
      xc,yc, r = c

      # transform coords
      xc,yc = self.parent.CoordBitmapToScreen(xc,yc)
      r *= scale

      pen = self.pen
      brush = self.brush
      # determine fill and stroke
      if c == self.active_circle:
        if self.action & self.ACTION_RESIZE:
          pen = self.resize_pen
          brush = self.active_brush
        elif self.action & self.ACTION_MOVE:
          pen = self.move_pen
          brush = self.active_brush
        else:
          pen = self.active_pen
          brush = self.active_brush
      gcdc.SetBrush(brush)
      gcdc.SetPen(pen)
      gcdc.DrawCircle(xc, yc, r)

    if self.action == self.ACTION_NONE and self.coords is not None:
      gcdc.SetPen(self.place_pen)
      gcdc.SetBrush(self.place_brush)
      x,y = self.parent.CoordBitmapToScreen(*self.coords)
      
      r = self.radius * scale

      gcdc.DrawCircle(x, y, r)

  def SetRadius(self, radius):
    self.radius = radius
    self.parent.Refresh()

