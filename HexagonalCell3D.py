#!/usr/bin/env python
import numpy as np
import ROOT as ro
from Cell3D import Cell3D

class HexagonalCell3D(Cell3D):
	def __init__(self, col_num=0, row_num=0, height=0, width_pitch_ratio=0, run=0):
		Cell3D.__init__(self, col_num, row_num, sides=6, height=height, width_pitch_ratio=width_pitch_ratio, run=run)
		self.col_3d_rx = min(self.p - self.w / 2.0, self.w / 4.0)
		self.col_3d_ry = min(self.h / (2.0 * np.sqrt(3, dtype='f8')), self.h * self.w / (4.0 * np.sqrt(np.power(self.w, 2, dtype='f8') - 4.0 * np.power(self.w - self.p, 2, dtype='f8'), dtype='f8')))

	def CreateTCutG(self):
		tempx = self.GetXCoordinatesPolygon(self.xcenter)
		tempy = self.GetYCoordinatesPolygon(self.ycenter)
		tempname = 'cutg_dia_' + str(self.run) + '_{c}_{r}_hex'.format(c=self.col_num, r=self.row_num)
		self.cutg = ro.TCutG(tempname, 7, tempx, tempy)
		self.cutg.SetNameTitle(tempname, tempname)
		self.cutg.SetVarX('diaChXPred')
		self.cutg.SetVarY('diaChYPred')
		self.cutg.SetLineColor(ro.kGray)
		self.cutg.SetLineWidth(2)

		self.SetCutReadOut(tempname)

		for p in xrange(self.sides):
			self.cutg_bias.append(self.GetBiasColumnCut(tempx[p], tempy[p], tempname))

	def GetBiasColumnCut(self, x0, y0, cutCellName):
		# return '(({cn})&&(({ry}*(diaChXPred-{x0}))^2+({rx}*(diaChYPred-{y0}))^2<({rx}*{ry})^2))'.format(cn=cutCellName, x0=x0, y0=y0, rx=self.col_3d_rx, ry=self.col_3d_ry)
		return '(({cn})&&(({ry}*(diaChXPred-{x0}))^2+({rx}*(diaChYPred-{y0}))^2<({rxrySq}))'.format(cn=cutCellName, x0=x0, y0=y0, rx=self.col_3d_rx, ry=self.col_3d_ry, rxrySq=np.power(self.col_3d_rx * self.col_3d_ry, 2.0, dtype='f8'))

	def CreateTCutGCenter(self):
		tempx = self.GetXCoordinatesPolygon(self.xcenter, 0.5)
		tempy = self.GetYCoordinatesPolygon(self.ycenter, 0.5)
		tempname = 'cutg_dia_' + str(self.run) + '_center_{c}_{r}_hex'.format(c=self.col_num, r=self.row_num)
		self.cutg_center = ro.TCutG(tempname, 7, tempx, tempy)
		self.cutg_center.SetNameTitle(tempname, tempname)
		self.cutg_center.SetVarX('diaChXPred')
		self.cutg_center.SetVarY('diaChYPred')
		self.cutg_center.SetLineColor(ro.kRed)
		self.cutg_center.SetLineWidth(2)

	def GetXCoordinatesPolygon(self, xcenter=0, fraction=1.0):
		return np.add(xcenter, np.multiply(np.divide(np.array([-(2.0 * self.p - self.w), -self.w, -(2.0 * self.p - self.w), 2.0 * self.p - self.w, self.w, 2.0 * self.p - self.w, -(2.0 * self.p - self.w)], 'f8'), 2.0, dtype='f8'), fraction, dtype='f8'), dtype='f8')

	def GetYCoordinatesPolygon(self, ycenter=0, fraction=1.0):
		return np.add(ycenter, np.multiply(np.divide(np.array([-self.h, 0, self.h, self.h, 0, -self.h, -self.h], 'f8'), 2.0, dtype='f8'), fraction, dtype='f8'), dtype='f8')

if __name__ == '__main__':
	z = HexagonalCell3D()