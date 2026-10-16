# -*- coding: utf-8 -*-
"""Composants de présentation de l'accueil. Aucun accès base ou réseau."""
import datetime as dt
import math
import wx
from Utils import UTILS_Ephemerides as data

INK = '#243f49'
MUTED = '#536c76'
TEAL = '#17656a'
SKY = '#eaf4fa'


def font(control, delta=0, bold=False):
    result = wx.Font(control.GetFont())
    result.SetPointSize(max(8, result.GetPointSize() + delta))
    if bold:
        result = result.Bold()
    return result


class Bandeau(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent, style=wx.TAB_TRAVERSAL)
        self.items, self.offset, self.message = [], 0, ''
        self.date = dt.date.today()
        self.SetMinSize(self.FromDIP((100, 40)))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.paint)
        self.Bind(wx.EVT_MOUSEWHEEL, self.wheel)

    def update(self, date, items, error=''):
        self.date, self.items, self.offset = date, items, 0
        self.message = 'Programme indisponible' if error else ''
        self.SetToolTip(error or 'Effectifs prévus, pas un pointage en temps réel.\n' + '\n'.join('%s : %s participants réservés ou pointés présents' %
                                         (i['name'], i['total']) for i in items) or
                        'Aucune activité programmée aujourd’hui parmi les activités choisies.')
        self.Refresh()

    def wheel(self, event):
        self.offset = max(0, min(getattr(self, 'overflow', 0), self.offset - event.GetWheelRotation() // 3))
        self.Refresh()

    def paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        dc.SetTextForeground(INK)
        dc.SetFont(font(self, bold=True))
        pad = self.FromDIP(6)
        date_text = '%s %d\n%s %s' % (
            ('Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche')[self.date.weekday()],
            self.date.day, ('Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
                            'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre')[self.date.month-1],
            self.date.strftime('%y'))
        dc.DrawText(date_text, pad, pad)
        date_width = max(dc.GetTextExtent(t)[0] for t in date_text.splitlines()) + pad * 3
        dc.SetClippingRegion(date_width, 0, max(1, self.GetClientSize().width-date_width), self.GetClientSize().height)
        x = date_width-self.offset
        if self.message:
            dc.SetFont(font(self))
            dc.DrawText(self.message, x, pad*2)
        for item in self.items:
            dc.SetFont(font(self))
            label = item['label'] + ' : '
            dc.DrawText(label, x, pad*2)
            x += dc.GetTextExtent(label)[0]
            dc.SetFont(font(self, -1, True))
            if item['alsh']:
                value = 'M %s\nA %s' % (item['morning'] if item['morning'] is not None else '—',
                                        item['afternoon'] if item['afternoon'] is not None else '—')
                dc.DrawText(value, x, pad)
                x += max(dc.GetTextExtent(t)[0] for t in value.splitlines())
            else:
                value = str(item['total'])
                dc.DrawText(value, x, pad*2)
                x += dc.GetTextExtent(value)[0]
            x += pad*3
        dc.DestroyClippingRegion()
        self.overflow = max(0, x+self.offset-self.GetClientSize().width)


class Meteo(wx.Panel):
    def __init__(self, parent, on_details):
        super().__init__(parent, style=wx.TAB_TRAVERSAL | wx.WANTS_CHARS)
        self.rows, self.error, self.description = [], '', ''
        self.on_details = on_details
        self.SetMinSize(self.FromDIP((320, 214)))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.Bind(wx.EVT_PAINT, self.paint)
        self.Bind(wx.EVT_LEFT_UP, self.open_details)
        self.Bind(wx.EVT_KEY_DOWN, self.key)

    def key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_SPACE):
            self.open_details(event)
        else:
            event.Skip()

    def open_details(self, event):
        if self.rows:
            self.on_details(event)

    def set_forecast(self, rows, error='', stamp=''):
        dates = sorted({r['date'] for r in rows})[:4]
        self.rows = [r for r in rows if r['date'] in dates]
        self.error = error
        self.description = '\n\n'.join('%s · %s\n%s' % (r['date'], r['period'], data.weather_text(r)) for r in self.rows)
        self.SetToolTip(('Source : Open-Meteo\nRelevé UTC : %s\n%s' % (stamp, error)).strip())
        self.SetName('Météo. ' + (self.description or error))
        self.Refresh()

    def GetLabel(self):
        return self.description or self.error

    def SetLabel(self, value):
        self.description = value

    def Wrap(self, width):
        pass  # Géométrie des deux périodes indépendante de la longueur des phrases.

    def icon(self, dc, x, y, code):
        severity = data.category(code)[0]
        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.Pen(TEAL, 2))
        gc.SetBrush(wx.Brush(SKY))
        if severity == 1:
            gc.SetPen(wx.Pen('#aa6909', 2))
            gc.DrawEllipse(x+5, y+3, 12, 12)
            for angle in range(0, 360, 45):
                a = math.radians(angle)
                gc.StrokeLine(x+11+9*math.cos(a), y+9+9*math.sin(a),
                              x+11+12*math.cos(a), y+9+12*math.sin(a))
        elif severity:
            gc.DrawEllipse(x+1, y+7, 14, 12)
            gc.DrawEllipse(x+9, y+2, 16, 17)
            gc.DrawRoundedRectangle(x+3, y+10, 25, 10, 5)
            if severity == 4:
                gc.StrokeLine(x+9, y+22, x+7, y+26)
                gc.StrokeLine(x+19, y+22, x+17, y+26)
            elif severity == 3:
                gc.StrokeLine(x+1, y+23, x+27, y+23)
                gc.StrokeLine(x+5, y+27, x+23, y+27)
            elif severity == 5:
                for cx in (x+8, x+21):
                    gc.StrokeLine(cx-3, y+24, cx+3, y+24)
                    gc.StrokeLine(cx, y+21, cx, y+27)
            elif severity == 6:
                bolt = gc.CreatePath()
                bolt.MoveToPoint(x+16, y+18)
                bolt.AddLineToPoint(x+10, y+25)
                bolt.AddLineToPoint(x+15, y+25)
                bolt.AddLineToPoint(x+10, y+31)
                gc.StrokePath(bolt)

    def paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(SKY)); dc.Clear()
        dc.SetFont(font(self, -1)); dc.SetTextForeground(MUTED)
        scale = self.GetDPIScaleFactor()
        # Tout dessin est en unités logiques : DC se charge du DPI Windows.
        dc.SetUserScale(scale, scale)
        dc.DrawText('Matin', 55, 4); dc.DrawText('Après-midi', 185, 4)
        dates = sorted({r['date'] for r in self.rows})[:4]
        for index, date in enumerate(dates):
            y = 28+index*46
            day = dt.date.fromisoformat(date)
            dc.SetFont(font(self, -1, True)); dc.SetTextForeground(INK)
            dc.DrawText(('Lun.', 'Mar.', 'Mer.', 'Jeu.', 'Ven.', 'Sam.', 'Dim.')[day.weekday()], 5, y)
            dc.DrawText(day.strftime('%d/%m'), 5, y+15)
            for period, (label, _, _) in enumerate(data.PERIODS):
                row = next((r for r in self.rows if r['date']==date and r['period']==label), None)
                x = 55+130*period
                if row is None:
                    dc.DrawText('—', x+35, y)
                    continue
                self.icon(dc, x, y, row.get('weather_code'))
                temp = row.get('temperature_2m')
                dc.SetFont(font(self, 1)); dc.SetTextForeground(INK)
                dc.DrawText('%g–%g°' % (round(temp[0]), round(temp[1])) if temp else '—', x+32, y)
                rain, wind = row.get('precipitation'), row.get('wind_speed_10m')
                arrow = data.wind_arrow(row.get('wind_direction_10m')) if wind else '—'
                dc.SetFont(font(self, -1)); dc.SetTextForeground(MUTED)
                text = '%s mm   %s km/h %s' % ('—' if rain is None else '%g' % round(rain, 1),
                                              '—' if wind is None else '%g' % round(wind), arrow)
                dc.DrawText(text, x, y+24)
        if not dates or self.error:
            dc.SetFont(font(self, -1)); dc.SetTextForeground(MUTED)
            dc.DrawText('Météo indisponible' if not dates else 'Données en cache · voir détail', 5, 210 if dates else 32)
