#!/usr/bin/env python
# from ROOT import TFile, TH2F, TH3F, TH1F, TCanvas, TCutG, kRed, gStyle, TBrowser, Long, TF1
from optparse import OptionParser
# from numpy import array, floor, average, std
import numpy as np
import ROOT as ro
import ipdb  # set_trace, launch_ipdb_on_exception
import progressbar
from copy import deepcopy
from collections import OrderedDict
from NoiseExtraction import NoiseExtraction
import os, sys, shutil
from Utils import *
import cPickle as pickle

__author__ = 'DA'

dicTypes = {'Char_t': 'int8', 'UChar_t': 'uint8', 'Short_t': 'short', 'UShort_t': 'ushort', 'Int_t': 'int32', 'UInt_t': 'uint32', 'Float_t': 'float32', 'Double_t': 'float64', 'Long64_t': 'int64',
            'ULong64_t': 'uint64', 'Bool_t': 'bool'}

diaChs = 128

fillColor = ro.TColor.GetColor(125, 153, 209)
sigma_axis = {'min': 0, 'max': 35}
adc_axis = {'min': 0, 'max': 2**12 - 1}
ped_axis = {'min': 0, 'max': 2**12 - 1}
cm_axis = {'min': -100, 'max': 100}


class PedestalAnalysis:
	def __init__(self, run=22011, dir='', force=False):
		print 'Creating PedestalAnalysis instance for run:', run
		self.run = run
		self.dir = dir + '/{r}'.format(r=self.run)
		self.force = force
		self.bar = None
		self.rootFile = self.pedTree = None
		self.adc_vect = self.ped_vect = self.sigma_vect = self.cm_vect = self.ped_cmc_vect = self.sigma_cmc_vect = None
		self.signal_vect, self.signal_cmc_vect = None, None
		self.adc_hist, self.ped_hist, self.sigma_hist, self.cm_hist, self.ped_cmc_hist, self.sigma_cmc_hist = ro.TH3F(), ro.TH3F(), ro.TH3F(), ro.TH2F(), ro.TH3F(), ro.TH3F()
		self.signal_hist, self.signal_cmc_hist, self.biggest_adc_hist = ro.TH2F(), ro.TH2F(), ro.TH2F()
		self.ped_ch_hist, self.ped_cmc_ch_hist, self.sigma_ch_hist, self.sigma_cmc_ch_hist = ro.TH2F(), ro.TH2F(), ro.TH2F(), ro.TH2F()
		self.dicBraNames = {'rawTree.DiaADC': 'adc_' + str(self.run), 'diaPedestalMean': 'ped_' + str(self.run), 'diaPedestaSigma': 'sigma_' + str(self.run),
		                    'diaPedestalMeanCMN': 'ped_cmc_' + str(self.run), 'diaPedestaSigmaCMN': 'sigma_cmc_' + str(self.run), 'commonModeNoise': 'cm_' + str(self.run)}
		self.allBranches = self.dicBraNames.keys()
		self.listBraNames1ch = ['commonModeNoise']
		self.listBraNamesChs = [x for x in self.allBranches if x not in self.listBraNames1ch]
		self.dicNewHistoNames = {'signal': 'signal_' + str(self.run), 'signalCMN': 'signal_cmc_' + str(self.run), 'biggestADC': 'biggest_adc_' + str(self.run), 'ped_ch': 'pedestal_ch_' + str(self.run),
		                         'pedCMN_ch': 'pedestal_cmc_ch_' + str(self.run), 'sigma_ch': 'sigma_ch_' + str(self.run), 'sigmaCMN_ch': 'sigma_cmc_ch_' + str(self.run)}
		self.allNewHistos = self.dicNewHistoNames.keys()
		self.dicBraVectChs = {}
		self.dicBraVect1ch = {}
		self.dicNewVectChs = {}
		self.dicNewVect1ch = {}
		self.entries = 0
		self.dicBraHist = {}
		self.dicNewHist = {}
		self.ev_axis = {'min': 0, 'max': 0, 'bins': 1000}
		self.ch_axis = {'min': -0.5, 'max': diaChs - 0.5, 'bins': diaChs}
		self.dicBraProf = {}
		self.tcutg_gr = None
		self.tcutg_dia = None
		self.tcutg_chs = {}
		self.gr, self.low_ch, self.up_ch = 0, 0, 0
		self.gr_plots, self.dia_channels_plots, self.nc_channels_plots = {}, {}, {}
		self.event_plots = {}
		self.event_list = None
		self.dia_channel_list = None
		self.nc_channel_list = None
		self.dic_bra_mean_ped_chs = {}
		self.dic_bra_sigma_ped_chs = {}
		self.cm_adc = None

		if self.force:
			self.ClearOldAnalysis()

		self.dicHasVectors = {bra: False for bra in self.allBranches}
		self.hasVectors = self.CheckVectorPickles()

		self.dicHasHistos = {bra: False for bra in self.allBranches}
		self.dicHasNewHistos = {bra: False for bra in self.allNewHistos}
		self.hasHistos = self.CheckHistograms()

		self.dicHasProfiles = {bra: False for bra in self.listBraNamesChs}
		self.hasProfiles = self.CheckProfiles()

		self.LoadROOTFile()
		if not self.hasVectors:
			self.LoadVectorsFromBranches()
			self.SaveVectorsPickles()
		else:
			self.LoadVectorsFromPickles()
		if not self.hasHistos:
			self.CreateHistograms()
			self.FillHistograms()
			self.SaveHistograms()
		else:
			self.LoadHistograms()
		if not self.hasProfiles:
			self.CreateProfiles()
			self.SaveProfiles()
		else:
			self.LoadProfiles()
		self.GetMeanSigmaPerChannel()

	def ClearOldAnalysis(self):
		if os.path.isdir('{d}/pedestalAnalysis/histos'.format(d=self.dir)):
			shutil.rmtree('{d}/pedestalAnalysis/histos'.format(d=self.dir))
		if os.path.isdir('{d}/pedestalAnalysis/profiles'.format(d=self.dir)):
			shutil.rmtree('{d}/pedestalAnalysis/profiles'.format(d=self.dir))

	def CheckVectorPickles(self):
		if not os.path.isdir('{d}/pedestalAnalysis/vectors'.format(d=self.dir)):
			print 'Pedestal analysis "vectors" does not exist. All the vectors for the analysis will be created'
			return False
		else:
			for branch in self.allBranches:
				name = self.dicBraNames[branch]
				self.dicHasVectors[branch] = True if os.path.isfile('{d}/pedestalAnalysis/vectors/{n}.dat'.format(d=self.dir, n=name)) else False
			return np.array(self.dicHasVectors.values(), '?').all()

	def CheckHistograms(self):
		if not os.path.isdir('{d}/pedestalAnalysis/histos'.format(d=self.dir)):
			print 'Pedestal analysis directory "histos" does not exist. All the histograms for the analysis will be created'
			return False
		else:
			for branch in self.allBranches:
				name = self.dicBraNames[branch]
				if os.path.isfile('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=name)):
					self.dicHasHistos[branch] = True
					tempf = ro.TFile('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=name), 'READ')
					self.dicBraHist[branch] = deepcopy(tempf.Get(name))
					tempf.Close()
					del tempf
				else:
					self.dicHasHistos[branch] = False

			for hist in self.allNewHistos:
				name = self.dicNewHistoNames[hist]
				if os.path.isfile('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=name)):
					self.dicHasNewHistos[hist] = True
					tempf = ro.TFile('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=name), 'READ')
					self.dicNewHist[hist] = deepcopy(tempf.Get(name))
					tempf.Close()
					del tempf
				else:
					self.dicHasNewHistos[hist] = False
			return np.array(self.dicHasHistos.values(), '?').all() and np.array(self.dicHasNewHistos.values(), '?').all()

	def CheckProfiles(self):
		if not os.path.isdir('{d}/pedestalAnalysis/profiles'.format(d=self.dir)):
			print 'Pedestal analysis directory "profiles" does not exist.'
			return False
		else:
			for branch in self.listBraNamesChs:
				name = self.dicBraNames[branch]
				if os.path.isfile('{d}/pedestalAnalysis/profiles/{n}_pyx.root'.format(d=self.dir, n=name)):
					self.dicHasProfiles[branch] = True
					tempf = ro.TFile('{d}/pedestalAnalysis/profiles/{n}_pyx.root'.format(d=self.dir, n=name), 'READ')
					self.dicBraProf[branch] = deepcopy(tempf.Get(name))
					tempf.Close()
					del tempf
				else:
					self.dicHasProfiles[branch] = False
			return np.array(self.dicHasProfiles.values(), '?').all()

	def LoadROOTFile(self):
		print 'Loading ROOT file...',
		sys.stdout.flush()
		# ipdb.set_trace()
		self.rootFile = ro.TFile('{d}/pedestalData.{r}.root'.format(d=self.dir, r=self.run), 'READ')
		self.pedTree = self.rootFile.Get('pedestalTree')
		self.entries = self.pedTree.GetEntries()
		# self.entries = int(maxEntries)
		print 'Done'

	def LoadVectorsFromBranches(self, first_ev=0):
		print 'Loading vectors from branches...'
		if self.pedTree is None:
			self.LoadROOTFile()

		num_bra_chs = len(self.listBraNamesChs)
		if num_bra_chs < 1:
			print 'The dictionary of branches and vectors is empty! try again'
			return
		channels = self.pedTree.GetLeaf(self.listBraNamesChs[0]).GetLen()
		for branch in self.listBraNamesChs:
			if self.pedTree.GetLeaf(branch).GetLen() != channels:
				print 'The given branches have different sizes! try again'
				return
		leng = self.pedTree.Draw(':'.join(self.listBraNamesChs), '', 'goff para', self.entries, first_ev)
		if leng == -1:
			print 'Error, could not load the branches. try again'
			return
		while leng > self.pedTree.GetEstimate():
			self.pedTree.SetEstimate(leng)
			leng = self.pedTree.Draw(':'.join(self.listBraNamesChs), '', 'goff para', self.entries, first_ev)
		self.entries = leng / channels
		for pos, branch in enumerate(self.listBraNamesChs):
			print 'Loading', branch, '...', ;sys.stdout.flush()
			temp = self.pedTree.GetVal(pos)
			self.dicBraVectChs[branch] = np.array([[temp[ev * channels + ch] for ch in xrange(channels)] for ev in xrange(self.entries)], dtype='f8')
			del temp
			print 'Done'

		num_bra_1ch = len(self.listBraNames1ch)
		if num_bra_1ch < 1:
			print 'The dictionary of branches and vectors is empty! try again'
			return
		channel = 1
		for branch in self.listBraNames1ch:
			if self.pedTree.GetLeaf(branch).GetLen() != channel:
				print 'The given branches have different sizes different to 1! try again'
				return
		leng = self.pedTree.Draw(':'.join(self.listBraNames1ch), '', 'goff para', self.entries, first_ev)
		if leng == -1:
			print 'Error, could not load the branches. try again'
			return
		while leng > self.pedTree.GetEstimate():
			self.pedTree.SetEstimate(leng)
			leng = self.pedTree.Draw(':'.join(self.listBraNames1ch), '', 'goff para', self.entries, first_ev)
		for pos, branch in enumerate(self.listBraNames1ch):
			print 'Loading', branch, '...', ;sys.stdout.flush()
			temp = self.pedTree.GetVal(pos)
			self.dicBraVect1ch[branch] = np.array([temp[ev] for ev in xrange(self.entries)], dtype='f8')
			del temp
			print 'Done'
		self.AssignVectorsFromDictrionaries()
		self.LoadNewVectorsFromVectors()
		self.ev_axis['max'] = self.entries

	def AssignVectorsFromDictrionaries(self):
		self.adc_vect, self.ped_vect, self.sigma_vect, self.ped_cmc_vect, self.sigma_cmc_vect = self.dicBraVectChs['rawTree.DiaADC'], self.dicBraVectChs['diaPedestalMean'], self.dicBraVectChs[
			'diaPedestaSigma'], self.dicBraVectChs['diaPedestalMeanCMN'], self.dicBraVectChs['diaPedestaSigmaCMN']
		self.cm_vect = self.dicBraVect1ch['commonModeNoise']

	def LoadNewVectorsFromVectors(self):
		self.dicNewVectChs['signal'] = self.adc_vect - self.ped_vect
		self.dicNewVectChs['signalCMN'] = np.subtract(self.adc_vect - self.ped_vect, [[cmi] for cmi in self.cm_vect])
		self.signal_vect = self.dicNewVectChs['signal']
		self.signal_cmc_vect = self.dicNewVectChs['signalCMN']

	def SaveVectorsPickles(self):
		print 'Saving vectors...'
		if not os.path.isdir('{d}/pedestalAnalysis/vectors'.format(d=self.dir)):
			os.makedirs('{d}/pedestalAnalysis/vectors'.format(d=self.dir))
		for branch in self.allBranches:
			print 'Saving', branch, '...', ; sys.stdout.flush()
			name = self.dicBraNames[branch]
			if branch in self.listBraNamesChs:
				with open('{d}/pedestalAnalysis/vectors/{n}.dat'.format(d=self.dir, n=name), 'wb') as fs:
					pickle.dump(self.dicBraVectChs[branch], fs, pickle.HIGHEST_PROTOCOL)
			else:
				with open('{d}/pedestalAnalysis/vectors/{n}.dat'.format(d=self.dir, n=name), 'wb') as fs:
					pickle.dump(self.dicBraVect1ch[branch], fs, pickle.HIGHEST_PROTOCOL)
			print 'Done'

	def LoadVectorsFromPickles(self):
		print 'Loading vectors from pickles...'
		for branch in self.allBranches:
			print 'Loading', branch, '...', ; sys.stdout.flush()
			name = self.dicBraNames[branch]
			if branch in self.listBraNamesChs:
				self.dicBraVectChs[branch] = pickle.load(open('{d}/pedestalAnalysis/vectors/{n}.dat'.format(d=self.dir, n=name), 'rb'))
			else:
				self.dicBraVect1ch[branch] = pickle.load(open('{d}/pedestalAnalysis/vectors/{n}.dat'.format(d=self.dir, n=name), 'rb'))
			print 'Done'
		self.AssignVectorsFromDictrionaries()
		self.LoadNewVectorsFromVectors()
		self.ev_axis['max'] = self.entries
		print

	def CreateHistograms(self):
		print 'Creating histograms...',
		sys.stdout.flush()
		# self.SetHistogramLimits()
		for branch in self.allBranches:
			if not self.dicHasHistos[branch]:
				name = self.dicBraNames[branch]
				if branch in self.listBraNames1ch:
					ymin, ymax, ybins = 0, 0, 0
					if name.startswith('cm'):
						ymin, ymax, ybins = cm_axis['min'], cm_axis['max'], int((cm_axis['max'] - cm_axis['min']) / 0.5)
					self.dicBraHist[branch] = ro.TH2F(name, name, self.ev_axis['bins'], self.ev_axis['min'], self.ev_axis['max'], ybins + 1, ymin, ymax + (ymax - ymin) / float(ybins))
					self.dicBraHist[branch].GetXaxis().SetTitle('event')
					self.dicBraHist[branch].GetYaxis().SetTitle(name[:-6])
				elif branch in self.listBraNamesChs:
					zmin, zmax, zbins = 0, 0, 0
					if name.startswith('ped'):
						zmin, zmax, zbins = ped_axis['min'], ped_axis['max'], int(min((ped_axis['max'] - ped_axis['min']) / 5., 1000))
					elif name.startswith('adc'):
						zmin, zmax, zbins = adc_axis['min'], adc_axis['max'], int(min((adc_axis['max'] - adc_axis['min']) / 5., 1000))
					elif name.startswith('sigma'):
						zmin, zmax, zbins = sigma_axis['min'], sigma_axis['max'], int(min((sigma_axis['max'] - sigma_axis['min']) / 0.1, 1000))
					self.dicBraHist[branch] = ro.TH3F(name, name, self.ev_axis['bins'], self.ev_axis['min'], self.ev_axis['max'], self.ch_axis['bins'], self.ch_axis['min'], self.ch_axis['max'], zbins + 1,
					                                  zmin, zmax + (zmax - zmin) / float(zbins))
					self.dicBraHist[branch].GetXaxis().SetTitle('event')
					self.dicBraHist[branch].GetYaxis().SetTitle('channel')
					self.dicBraHist[branch].GetZaxis().SetTitle(name[:-6])
		for hist in self.allNewHistos:
			if not self.dicHasNewHistos[hist]:
				name = self.dicNewHistoNames[hist]
				xmin, xmax, xbins = 0, 0, 0
				if name.startswith('signal'):
					xmin, xmax, xbins = -adc_axis['max'], adc_axis['max'], int(min(2*adc_axis['max'] / 0.5, 20000))
				elif name.startswith('biggest'):
					xmin, xmax, xbins = adc_axis['min'], adc_axis['max'], int(min((adc_axis['max'] - adc_axis['min']) / 0.5, 10000))
				elif name.startswith('ped'):
					xmin, xmax, xbins = ped_axis['max'], ped_axis['max'], int(min((ped_axis['max'] - ped_axis['min']) / 5.0, 1000))
				elif name.startswith('sigma'):
					xmin, xmax, xbins = sigma_axis['max'], sigma_axis['max'], int(min((sigma_axis['max'] - sigma_axis['min']) / 0.1, 1000))
				ymin, ymax, ybins = self.ch_axis['min'], self.ch_axis['max'], self.ch_axis['bins']
				self.dicNewHist[hist] = ro.TH2F(name, name, xbins, xmin, xmax, ybins, ymin, ymax)
				self.dicNewHist[hist].GetXaxis().SetTitle(name[:-6])
				self.dicNewHist[hist].GetYaxis().SetTitle('channel')
				self.dicNewHist[hist].GetZaxis().SetTitle('entries')

		self.adc_hist, self.ped_hist, self.sigma_hist, self.ped_cmc_hist, self.sigma_cmc_hist, self.cm_hist = self.dicBraHist['rawTree.DiaADC'], self.dicBraHist['diaPedestalMean'], self.dicBraHist[
			'diaPedestaSigma'], self.dicBraHist['diaPedestalMeanCMN'], self.dicBraHist['diaPedestaSigmaCMN'], self.dicBraHist['commonModeNoise']
		self.signal_hist, self.signal_cmc_hist, self.biggest_adc_hist = self.dicNewHist['signal'], self.dicNewHist['signalCMN'], self.dicNewHist['biggestADC']
		self.ped_ch_hist, self.ped_cmc_ch_hist, self.sigma_ch_hist, self.sigma_cmc_ch_hist = self.dicNewHist['ped_ch'], self.dicNewHist['pedCMN_ch'], self.dicNewHist['sigma_ch'], self.dicNewHist['sigmaCMN_ch']
		print 'Done'

	def FillHistograms(self):
		print 'Filling histograms:'
		self.CreateProgressBar(self.entries)
		if self.bar is not None:
			self.bar.start()
		biggest_adc_ch = self.adc_vect.argmax(axis=1)
		biggest_adc = self.adc_vect.max(axis=1)
		for ev in xrange(self.entries):
			for ch in xrange(diaChs):
				if not self.dicHasHistos['rawTree.DiaADC']:
					self.adc_hist.Fill(ev, ch, self.adc_vect.item(ev, ch))
				if not self.dicHasHistos['diaPedestalMean']:
					self.ped_hist.Fill(ev, ch, self.ped_vect.item(ev, ch))
				if not self.dicHasHistos['diaPedestaSigma']:
					self.sigma_hist.Fill(ev, ch, self.sigma_vect.item(ev, ch))
				if not self.dicHasHistos['diaPedestalMeanCMN']:
					self.ped_cmc_hist.Fill(ev, ch, self.ped_cmc_vect.item(ev, ch))
				if not self.dicHasHistos['diaPedestaSigmaCMN']:
					self.sigma_cmc_hist.Fill(ev, ch, self.sigma_cmc_vect.item(ev, ch))
				if not self.dicHasNewHistos['signal']:
					self.signal_hist.Fill(self.signal_vect.item(ev, ch), ch)
				if not self.dicHasNewHistos['signalCMN']:
					self.signal_cmc_hist.Fill(self.signal_cmc_vect.item(ev, ch), ch)
				if not self.dicHasNewHistos['ped_ch']:
					self.ped_ch_hist.Fill(self.ped_vect.item(ev, ch), ch)
				if not self.dicHasNewHistos['pedCMN_ch']:
					self.ped_ch_hist.Fill(self.ped_cmc_vect.item(ev, ch), ch)
				if not self.dicHasNewHistos['sigma_ch']:
					self.ped_ch_hist.Fill(self.sigma_vect.item(ev, ch), ch)
				if not self.dicHasNewHistos['sigmaCMN_ch']:
					self.ped_ch_hist.Fill(self.sigma_cmc_vect.item(ev, ch), ch)
			if not self.dicHasNewHistos['biggestADC']:
				self.biggest_adc_hist.Fill(biggest_adc.item(ev), biggest_adc_ch.item(ev))
			if not self.dicHasHistos['commonModeNoise']:
				self.cm_hist.Fill(ev, self.cm_vect.item(ev))
			if self.bar is not None:
				self.bar.update(ev + 1)
		if self.bar is not None:
			self.bar.finish()

	def SaveHistograms(self):
		print 'Saving histograms:'
		if not os.path.isdir('{d}/pedestalAnalysis/histos'.format(d=self.dir)):
			os.makedirs('{d}/pedestalAnalysis/histos'.format(d=self.dir))
		for branch, histo in self.dicBraHist.iteritems():
			if not self.dicHasHistos[branch]:
				name = self.dicBraNames[branch]
				histo.SaveAs('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=name))
				self.dicHasHistos[branch] = True
		for key, histo in self.dicNewHist.iteritems():
			if not self.dicHasNewHistos[key]:
				name = self.dicNewHistoNames[key]
				histo.SaveAs('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=name))
				self.dicHasNewHistos[key] = True

	def CreateProfiles(self):
		print 'Creating profiles:'
		self.dicBraProf = {branch: histo.Project3DProfile('yx') for branch, histo in self.dicBraHist.iteritems() if branch in self.listBraNamesChs and not self.dicHasProfiles[branch]}
		# for branch, histo in self.dicBraHist.iteritems():
		# 	if branch in self.listBraNamesChs:
		# 		self.dicBraProf[branch] = histo.Project3DProfile('yx')
		self.SetProfileDefaults()

	def SetProfileDefaults(self):
		for branch, prof in self.dicBraProf.iteritems():
			prof.GetXaxis().SetTitle('event')
			prof.GetYaxis().SetTitle('channel')
			prof.GetZaxis().SetTitle(self.dicBraNames[branch][:-6])
			prof.GetZaxis().SetRangeUser(self.dicBraHist[branch].GetZaxis().GetXmin(), self.dicBraHist[branch].GetZaxis().GetXmax())
			prof.SetStats(False)

	def SaveProfiles(self):
		print 'Saving profiles:'
		if not os.path.isdir('{d}/pedestalAnalysis/profiles'.format(d=self.dir)):
			os.makedirs('{d}/pedestalAnalysis/profiles'.format(d=self.dir))
		for branch, prof in self.dicBraProf.iteritems():
			if not self.dicHasProfiles[branch]:
				name = self.dicBraNames[branch]
				prof.SaveAs('{d}/pedestalAnalysis/profiles/{n}_pyx.root'.format(d=self.dir, n=name))
				self.dicHasProfiles[branch] = True

	def LoadHistograms(self):
		print 'Loading Histograms...',
		sys.stdout.flush()
		for branch in self.allBranches:
			if self.dicHasHistos[branch]:
				temp = ro.TFile('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=self.dicBraNames[branch]), 'read')
				self.dicBraHist[branch] = deepcopy(temp.Get(self.dicBraNames[branch]))
				temp.Close()
				del temp
		for hist in self.allNewHistos:
			if self.dicHasNewHistos[hist]:
				temp = ro.TFile('{d}/pedestalAnalysis/histos/{n}.root'.format(d=self.dir, n=self.dicNewHistoNames[hist]), 'read')
				self.dicNewHist[hist] = deepcopy(temp.Get(self.dicNewHistoNames[hist]))
				temp.Close()
				del temp
		self.entries = int(self.dicBraHist[self.listBraNamesChs[0]].GetXaxis().GetXmax())
		self.SetHistogramDefaults()
		print 'Done'

	def SetHistogramDefaults(self):
		for branch, hist in self.dicBraHist.iteritems():
			name = self.dicBraNames[branch]
			hist.GetXaxis().SetTitle('event')
			hist.GetYaxis().SetTitle('channel') if branch in self.listBraNamesChs else hist.GetYaxis().SetTitle(name[:-6])
			if branch in self.listBraNamesChs:
				hist.GetZaxis().SetTitle(name[:-6])
		for key, hist, in self.dicNewHist.iteritems():
			name = self.dicNewHistoNames[key]
			hist.GetXaxis().SetTitle(name[:-6])
			hist.GetYaxis().SetTitle('channel')
			hist.GetZaxis().SetTitle('entries')

	def GetMeanSigmaPerChannel(self):
		for branch, prof in self.dicBraProf.iteritems():
			# ipdb.set_trace()
			temp1 = prof.ProfileY(prof.GetTitle() + '_py')
			self.dic_bra_mean_ped_chs[branch] = np.array([temp1.GetBinContent(ch + 1) for ch in xrange(diaChs + 1)], dtype='f8')
			self.dic_bra_sigma_ped_chs[branch] = np.array([temp1.GetBinError(ch + 1) for ch in xrange(diaChs + 1)], dtype='f8')
			del temp1

	def SetTCutG(self, ev_ini=0, ev_end=0, color=ro.kRed + 3):
		ev_fin = self.entries if ev_end == 0 else ev_end

		self.tcutg_gr = ro.TCutG('TCutG_gr', 5)
		self.tcutg_gr.SetVarX('xaxis')
		self.tcutg_gr.SetVarY('yaxis')
		self.tcutg_gr.SetPoint(0, ev_ini, self.gr - 0.5)
		self.tcutg_gr.SetPoint(1, ev_ini, self.gr + 0.5)
		self.tcutg_gr.SetPoint(2, ev_fin, self.gr + 0.5)
		self.tcutg_gr.SetPoint(3, ev_fin, self.gr - 0.5)
		self.tcutg_gr.SetPoint(4, ev_ini, self.gr - 0.5)
		self.tcutg_gr.SetLineWidth(3)
		self.tcutg_gr.SetLineStyle(7)
		self.tcutg_gr.SetLineColor(color)

		self.tcutg_dia = ro.TCutG('TCutG_dia', 5)
		self.tcutg_dia.SetVarX('xaxis')
		self.tcutg_dia.SetVarY('yaxis')
		self.tcutg_dia.SetPoint(0, ev_ini, self.low_ch - 0.5)
		self.tcutg_dia.SetPoint(1, ev_ini, self.up_ch + 0.5)
		self.tcutg_dia.SetPoint(2, ev_fin, self.up_ch + 0.5)
		self.tcutg_dia.SetPoint(3, ev_fin, self.low_ch - 0.5)
		self.tcutg_dia.SetPoint(4, ev_ini, self.low_ch - 0.5)
		self.tcutg_dia.SetLineWidth(3)
		self.tcutg_dia.SetLineStyle(7)
		self.tcutg_dia.SetLineColor(color)

		for ch in xrange(self.low_ch, self.up_ch + 1):
			self.tcutg_chs[ch] = ro.TCutG('TCutG_ch_'+str(ch), 5)
			self.tcutg_chs[ch].SetVarX('xaxis')
			self.tcutg_chs[ch].SetVarY('yaxis')
			self.tcutg_chs[ch].SetPoint(0, ev_ini, ch - 0.5)
			self.tcutg_chs[ch].SetPoint(1, ev_ini, ch + 0.5)
			self.tcutg_chs[ch].SetPoint(2, ev_fin, ch + 0.5)
			self.tcutg_chs[ch].SetPoint(3, ev_fin, ch - 0.5)
			self.tcutg_chs[ch].SetPoint(4, ev_ini, ch - 0.5)
			self.tcutg_chs[ch].SetLineWidth(3)
			self.tcutg_chs[ch].SetLineStyle(7)
			self.tcutg_chs[ch].SetLineColor(color)

	def SetChannels(self):
		cont = False
		while not cont:
			temp = raw_input('Type the channel for the GR (should be between 0 and 127): ')
			if IsInt(temp):
				if 0 <= int(temp) < diaChs:
					self.gr = int(temp)
					cont = True
		cont = False
		while not cont:
			temp = raw_input('Type the lower channel to analyse (should be between 0 and 127): ')
			if IsInt(temp):
				if 0 <= int(temp) < diaChs:
					self.low_ch = int(temp)
					cont = True
		cont = False
		while not cont:
			temp = raw_input('Type the upper channel to analyse (should be between 0 and 127): ')
			if IsInt(temp):
				if 0 <= int(temp) < diaChs:
					self.up_ch = int(temp)
					cont = True
		self.dia_channel_list = range(self.low_ch, self.up_ch + 1)
		self.nc_channel_list = [ch for ch in xrange(diaChs) if ch not in self.dia_channel_list]
		self.SetTCutG()

	def GetChannelsHistos(self):
		for branch, prof in self.dicBraProf.iteritems():
			name = self.dicBraNames[branch]
			self.gr_plots[branch] = self.ProjectChannel(self.gr, prof, name)
		for ch in self.dia_channel_list:
			# self.dia_channels_plots[ch] = {}
			self.dia_channels_plots[ch] = {branch: self.ProjectChannel(ch, prof, self.dicBraNames[branch]) for branch, prof in self.dicBraProf.iteritems()}
			# for branch, prof in self.dicBraProf.iteritems():
			# 	name = self.dicBraNames[branch]
			# 	self.dia_channels_plots[ch][branch] = self.ProjectChannel(ch, prof, name)
		for ch in self.nc_channel_list:
			# self.nc_channels_plots[ch] = {}
			self.nc_channels_plots[ch] = {branch: self.ProjectChannel(ch, prof, self.dicBraNames[branch]) for branch, prof in self.dicBraProf.iteritems()}
			# for branch, prof in self.dicBraProf.iteritems():
			# 	name = self.dicBraNames[branch]
			# 	self.nc_channels_plots[ch][branch] = self.ProjectChannel(ch, prof, name)

	def GetEventsHistos(self):
		for branch, prof in self.dicBraProf.iteritems():
			name = self.dicBraNames[branch]
			for ev_bin in self.event_list:
				self.event_plots[branch] = self.ProjectEvent(ev_bin, prof, name)
		for branch in self.listBraNames1ch:
			name = self.dicBraNames[branch]
			hist = self.dicBraHist[branch]
			for ev_bin in self.event_list:
				self.event_plots[branch] = self.ProjectEvent(ev_bin, hist, name)

	def SetEventsList(self, bins=11, bin_low=0, bin_up=0):
		bin_l = 1 if bin_low == 0 else bin_low
		bin_u = self.ev_axis['bins'] if bin_up == 0 else bin_up
		n_bins = 1 if bin_l == bin_u else bins
		self.event_list = np.array(np.round(np.linspace(bin_l, bin_u, n_bins)), dtype='uint')

	def GetPlots(self):
		if self.gr == self.low_ch == self.up_ch:
			self.SetChannels()
		if len(self.gr_plots) == 0 or len(self.dia_channels_plots) == 0:
			self.GetChannelsHistos()
		if not self.event_list:
			self.SetEventsList()
		if len(self.event_plots) == 0:
			self.GetEventsHistos()

	def ProjectChannel(self, ch, prof, name):
		temp = prof.ProjectionX('' + name[:-6] + '_ch_' + str(ch), ch + 1, ch + 1)
		temp.SetTitle('' + name[:-6] + '_ch_' + str(ch))
		temp.GetXaxis().SetTitle('event')
		temp.GetYaxis().SetTitle(name[:-6])
		temp.SetFillColor(fillColor)
		temp.GetYaxis().SetRangeUser(prof.GetMinimum(), prof.GetMaximum())
		return temp

	def ProjectEvent(self, ev_bin, prof, name):
		event = int(round(prof.GetXaxis().GetBinCenter(int(ev_bin))))
		temp = prof.ProjectionY('' + name[:-6] + '_ev_' + str(event), int(ev_bin), int(ev_bin))
		temp.SetTitle('' + name[:-6] + '_ev_' + str(event))
		temp.GetXaxis().SetTitle('channel')
		temp.GetYaxis().SetTitle(name[:-6])
		temp.SetFillColor(fillColor)
		temp.GetYaxis().SetRangeUser(prof.GetMinimum(), prof.GetMaximum())
		return temp

	def LoadProfiles(self):
		print 'Loading Profiles...',
		sys.stdout.flush()
		for branch in self.listBraNamesChs:
			if self.dicHasProfiles[branch]:
				temp = ro.TFile('{d}/pedestalAnalysis/profiles/{n}_pyx.root'.format(d=self.dir, n=self.dicBraNames[branch]), 'read')
				self.dicBraProf[branch] = deepcopy(temp.Get('{n}_pyx'.format(n=self.dicBraNames[branch])))
				temp.Close()
				del temp
		self.entries = int(self.dicBraProf[self.listBraNamesChs[0]].GetXaxis().GetXmax())
		self.SetProfileDefaults()
		print 'Done'

	def LoadVectorFromBranch(self, branch):
		if self.dicHasVectors[branch]:
			self.LoadVectorFromPickle(branch)
		else:
			self.LoadVectorFromTree(branch)

	def LoadVectorFromPickle(self, branch):
		if branch in self.listBraNamesChs:
			self.dicBraVectChs[branch] = pickle.load(open('{d}/pedestalAnalysis/vectors/{n}dat'.format(d=self.dir, n=self.dicBraNames[branch]), 'rb'))
		else:
			self.dicBraVect1ch[branch] = pickle.load(open('{d}/pedestalAnalysis/vectors/{n}dat'.format(d=self.dir, n=self.dicBraNames[branch]), 'rb'))

	def LoadVectorFromTree(self, branch):
		channels = self.pedTree.GetLeaf(branch).GetLen()
		leng = self.pedTree.Draw(branch, '', 'goff', self.entries, 0)
		if leng == -1:
			print 'Error, could not load the branches. try again'
			return
		while leng > self.pedTree.GetEstimate():
			self.pedTree.SetEstimate(leng)
			leng = self.pedTree.Draw(branch, '', 'goff', self.entries, 0)
		temp = self.pedTree.GetVal(0)
		if branch in self.listBraNamesChs:
			self.dicBraVectChs[branch] = np.array([[temp[ev * channels + ch] for ch in xrange(channels)] for ev in xrange(self.entries)], dtype='f8')
		elif branch in self.listBraNames1ch:
			self.dicBraVect1ch[branch] = np.array([temp[ev] for ev in xrange(self.entries)], dtype='f8')
		del temp

	def SetHistogramLimits(self):
		for branch, vect in self.dicBraVect1ch.iteritems():
			name = self.dicBraNames[branch]
			if name.startswith('cm'):
				ymin, ymax = min(cm_axis['min'], vect.min()), max(cm_axis['max'], vect.max())
				cm_axis['min'], cm_axis['max'] = ymin, ymax
		for branch, vect in self.dicBraVectChs.iteritems():
			name = self.dicBraNames[branch]
			if name.startswith('ped'):
				zmin, zmax = min(ped_axis['min'], vect.min()), max(ped_axis['max'], vect.max())
				ped_axis['min'], ped_axis['max'] = zmin, zmax
			elif name.startswith('sigm'):
				zmin, zmax = min(sigma_axis['min'], vect.min()), max(sigma_axis['max'], vect.max())
				sigma_axis['min'], sigma_axis['max'] = zmin, zmax
			elif name.startswith('adc'):
				zmin, zmax = min(adc_axis['min'], vect.min()), max(adc_axis['max'], vect.max())
				adc_axis['min'], adc_axis['max'] = zmin, zmax

	def Calculate_CM_ADC(self):
		self.CheckExistanceVector('rawTree.DiaADC')
		self.adc_vect = self.dicBraVectChs['rawTree.DiaADC']
		self.CheckExistanceVector('commonModeNoise')
		self.cm_vect = self.dicBraVect1ch['commonModeNoise']
		temp = []
		self.CreateProgressBar(self.entries)
		if self.bar is not None:
			self.bar.start()
		for ev in xrange(self.entries):
			temp.append(self.adc_vect[ev].mean())
		self.cm_adc = np.array(temp, 'f8')
		del temp

	def CheckExistanceVector(self, branch):
		if branch in self.listBraNames1ch:
			if len(self.dicBraVect1ch) != 0:
				if self.dicBraVect1ch[branch]:
					return
		elif branch in self.listBraNamesChs:
			if len(self.dicBraVectChs) != 0:
				if self.dicBraVectChs[branch]:
					return
		if not self.pedTree:
			self.LoadROOTFile()
			self.LoadVectorFromBranch(branch)

	def CreateProgressBar(self, maxVal=1):
		widgets = [
			'Processed: ', progressbar.Counter(),
			' out of {mv} '.format(mv=maxVal), progressbar.Percentage(),
			' ', progressbar.Bar(marker='>'),
			' ', progressbar.Timer(),
			' ', progressbar.ETA()
			# ' ', progressbar.AdaptativeETA(),
			#  ' ', progressbar.AdaptativeTransferSpeed()
		]
		self.bar = progressbar.ProgressBar(widgets=widgets, maxval=maxVal)

if __name__ == '__main__':
	parser = OptionParser()
	parser.add_option('-r', '--run', dest='run', default=22022, type='int', help='Run to be analysed (e.g. 22022)')
	parser.add_option('-d', '--dir', dest='dir', default='.', type='string', help='source folder containing processed data of different runs')
	parser.add_option('-f', '--force', dest='force', default=False, action='store_true')

	(options, args) = parser.parse_args()
	run = int(options.run)
	dir = str(options.dir)
	force = bool(options.force)
	# output = str(options.output)
	# connect = int(options.connect)
	# low = int(options.low)
	# high = int(options.high)

	pedAna = PedestalAnalysis(run, dir, force)
