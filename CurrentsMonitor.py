#!/usr/bin/env python
# from ROOT import TFile, TH2F, TH3F, TH1F, TCanvas, TCutG, kRed, gStyle, TBrowser, Long, TF1
from optparse import OptionParser
from ConfigParser import ConfigParser
# from numpy import array, floor, average, std
import numpy as np
import ROOT as ro
import ipdb  # set_trace, launch_ipdb_on_exception
import progressbar
from copy import deepcopy
# from NoiseExtraction import NoiseExtraction
import os, sys, shutil
from Utils import *
import subprocess as subp
import multiprocessing as mp
import visa
import serial
import PyGnuplot as pygp

__author__ = 'DA'

dicTypes = {'Char_t': 'int8', 'UChar_t': 'uint8', 'Short_t': 'short', 'UShort_t': 'ushort', 'Int_t': 'int32', 'UInt_t': 'uint32', 'Float_t': 'float32', 'Double_t': 'float64', 'Long64_t': 'int64',
            'ULong64_t': 'uint64', 'Bool_t': 'bool'}

diaChs = 128

fillColor = ro.TColor.GetColor(125, 153, 209)
sigma_axis = {'min': 0, 'max': 35}
adc_axis = {'min': 0, 'max': 2**12}
ped_axis = {'min': 0, 'max': 2**12}
cm_axis = {'min': -100, 'max': 100}


class CurrentsMonitor:
	def __init__(self, filepath, inst='ASRL3::INSTR', refresh_time=2, hot_start=True):
		print 'Starting Currents Monitor'
		self.filepath = filepath
		self.hotStart = hot_start
		self.refreshT = refresh_time
		self.instAdd = inst
		self.rm = visa.ResourceManager('@py')
		self.inst = self.rm.open_resource(inst)
		self.r_time = refresh_time

		# self.scratch_path = '/scratch/strip_telescope_tests/runDiego/output'  # at snickers

		self.InitDevice()
		self.delete_old = False
		self.first_event = 0
		self.num_events = 0
		self.do_pedestal = False
		self.do_cluster = False
		self.do_selection = False
		self.do_alignment = False
		self.do_transparent = False
		self.do_3d = False

		self.sub_pro, self.sub_pro_e, self.sub_pro_o = None, None, None
		self.process_f = None
		self.process_e = None
		self.process_o = None
		ro.gStyle.SetPalette(55)
		ro.gStyle.SetNumberContours(999)

	def Configure(self):
		pass

	def ClearBuffer(self):
		cont = True
		while cont:
			temp = self.inst.read

	def InitDevice(self):
		self.serial = serial.Serial(port=self.instAdd, baudrate=9600, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=.5)


	def ReadInputFile(self, in_file=''):
		if in_file != '':
			if os.path.isfile(in_file):
				pars = ConfigParser()
				pars.read(in_file)
				print 'Loading job description from file:', in_file

				if pars.has_section('RUN'):
					if pars.has_option('RUN', 'StripTelescopeAnalysis_path'):
						self.StripTelescopeAnalysis_path = pars.get('RUN', 'StripTelescopeAnalysis_path')
					if pars.has_option('RUN', 'run'):
						self.run = pars.getint('RUN', 'run')
					else:
						ExitMessage('Must specify run under [RUN]. Exiting...')
					if pars.has_option('RUN', 'events'):
						self.total_events = pars.getint('RUN', 'events')
					else:
						ExitMessage('Must specify events under [RUN]. Exiting...')
					if pars.has_option('RUN', 'dia_input'):
						self.dia_input = pars.getint('RUN', 'dia_input')
					if pars.has_option('RUN', 'dia_saturation'):
						self.dia_saturation = pars.getint('RUN', 'dia_saturation')
					if pars.has_option('RUN', 'max_transparent_cluster_size'):
						self.max_transparent_cluster_size = pars.getint('RUN', 'max_transparent_cluster_size')
					if pars.has_option('RUN', 'datadir'):
						self.data_dir = pars.get('RUN', 'datadir')
					else:
						ExitMessage('Must specify datadir under [RUN]. Exiting...')
					if pars.has_option('RUN', 'outputdir'):
						self.out_dir = pars.get('RUN', 'outputdir')
					else:
						ExitMessage('Must specify outputdir under [RUN]. Exiting...')
					if pars.has_option('RUN', 'settingsdir'):
						self.settings_dir = pars.get('RUN', 'settingsdir')
					else:
						ExitMessage('Must specify settingsdir under [RUN]. Exiting...')
					if pars.has_option('RUN', 'runlistsdir'):
						self.run_lists_dir = pars.get('RUN', 'runlistsdir')
					else:
						ExitMessage('Must specify runlistsdir under [RUN]. Exiting...')
					if pars.has_option('RUN', 'subdir'):
						self.subdir = pars.get('RUN', 'subdir')
					if pars.has_option('RUN', 'do_even'):
						self.do_even = pars.getboolean('RUN', 'do_even')
					if pars.has_option('RUN', 'do_odd'):
						self.do_odd = pars.getboolean('RUN', 'do_odd')
					if pars.has_option('RUN', 'do_chs'):
						self.do_chs = pars.getboolean('RUN', 'do_chs')
					if pars.has_option('RUN', 'batch'):
						self.batch = pars.getboolean('RUN', 'batch')
					if pars.has_option('RUN', 'symlinks'):
						self.symlinks = pars.getboolean('RUN', 'symlinks')
					if pars.has_option('RUN', 'delete_old'):
						self.delete_old = pars.getboolean('RUN', 'delete_old')

				if pars.has_section('ANALYSIS'):
					if pars.has_option('ANALYSIS', 'first_event'):
						self.first_event = pars.getint('ANALYSIS', 'first_event')
					if pars.has_option('ANALYSIS', 'num_events'):
						self.num_events = pars.getint('ANALYSIS', 'num_events')
					if pars.has_option('ANALYSIS', 'do_pedestal'):
						self.do_pedestal = pars.getboolean('ANALYSIS', 'do_pedestal')
					if pars.has_option('ANALYSIS', 'do_cluster'):
						self.do_cluster = pars.getboolean('ANALYSIS', 'do_cluster')
					if pars.has_option('ANALYSIS', 'do_selection'):
						self.do_selection = pars.getboolean('ANALYSIS', 'do_selection')
					if pars.has_option('ANALYSIS', 'do_alignment'):
						self.do_alignment = pars.getboolean('ANALYSIS', 'do_alignment')
					if pars.has_option('ANALYSIS', 'do_transparent'):
						self.do_transparent = pars.getboolean('ANALYSIS', 'do_transparent')
					if pars.has_option('ANALYSIS', 'do_3d'):
						self.do_3d = pars.getboolean('ANALYSIS', 'do_3d')

				self.num_events = self.total_events if self.num_events == 0 else self.num_events
				return
		ExitMessage('Input file "{i}" does not exist. Must input a valid file. Exiting'.format(i=in_file))

	def Create_Run_List(self, do_single_ch=False):
		CreateDirectoryIfNecessary(self.run_lists_dir)
		ped = 1 if self.do_pedestal else 0
		clu = 1 if self.do_cluster else 0
		sele = 1 if self.do_selection else 0
		alig = 1 if self.do_alignment else 0
		tran = 1 if self.do_transparent else 0
		CreateDirectoryIfNecessary(self.run_lists_dir+'/{f}'.format(f=self.subdir))
		with open(self.run_lists_dir + '/{f}/RunList_'.format(f=self.subdir)+str(self.run)+'.ini', 'w') as rlf:
			rlf.write('{r}\t0\t0\t{n}\t0\t{p}\t{c}\t{s}\t{al}\t0\t{t}\n#\n'.format(r=self.run, n=self.num_events, p=ped, c=clu, s=sele, al=alig, t=tran))
		if self.do_even or self.do_odd:
			CreateDirectoryIfNecessary(self.run_lists_dir+'/'+self.subdir+'/odd')
			with open(self.run_lists_dir+'/'+self.subdir+'/odd' + '/RunList_'+str(self.run)+'.ini', 'w') as rlf:
				rlf.write('{r}\t0\t0\t{n}\t0\t0\t0\t0\t0\t0\t0\n#\n'.format(r=self.run, n=self.num_events, p=ped, c=clu, s=sele))
			CreateDirectoryIfNecessary(self.run_lists_dir+'/'+self.subdir+'/even')
			with open(self.run_lists_dir+'/'+self.subdir+'/even' + '/RunList_'+str(self.run)+'.ini', 'w') as rlf:
				rlf.write('{r}\t0\t0\t{n}\t0\t0\t0\t0\t0\t0\t0\n#\n'.format(r=self.run, n=self.num_events, p=ped, c=clu, s=sele))
		if do_single_ch:
			CreateDirectoryIfNecessary(self.run_lists_dir+'/'+self.subdir+'/channels')
			with open(self.run_lists_dir + '/' + self.subdir + '/channels/RunList_' + str(self.run) + '.ini', 'w') as rlf:
				rlf.write('{r}\t0\t0\t{n}\t0\t0\t0\t0\t0\t0\t0\n#\n'.format(r=self.run, n=self.num_events, p=ped, c=clu, s=sele))

	def Check_settings_file(self):
		if not os.path.isdir(self.settings_dir + '/' + self.subdir):
			os.makedirs(self.settings_dir + '/' + self.subdir)
		if not os.path.isfile(self.settings_dir + '/' + self.subdir + '/settings.{r}.ini'.format(r=self.run)):
			CreateDefaultSettingsFile(self.settings_dir + '/' + self.subdir, self.run, self.total_events, ev_ini=self.first_event, num_evs_ana=self.num_events, dia_input=self.dia_input, dia_sat=self.dia_saturation, max_trans_clust=self.max_transparent_cluster_size)
		if self.do_even or self.do_odd:
			self.Copy_settings_to_even_odd()

	def Copy_settings_to_even_odd(self):
		if not os.path.isdir(self.settings_dir + '/'+self.subdir+'/even'):
			os.makedirs(self.settings_dir + '/'+self.subdir+'/even')
		if not os.path.isdir(self.settings_dir + '/'+self.subdir+'/odd'):
			os.makedirs(self.settings_dir + '/'+self.subdir+'/odd')
		shutil.copy(self.settings_dir + '/'+self.subdir+'/settings.{r}.ini'.format(r=self.run), self.settings_dir + '/'+self.subdir+'/even/')
		shutil.copy(self.settings_dir + '/'+self.subdir+'/settings.{r}.ini'.format(r=self.run), self.settings_dir + '/'+self.subdir+'/odd/')
		self.Modify_even_odd()

	def Modify_even_odd(self):
		self.Modify_even()
		self.Modify_odd()

	def Modify_even(self):
		print 'Modifying even settings file...', ; sys.stdout.flush()
		Replace_Settings_Line(self.settings_dir + '/even/settings.{r}.ini'.format(r=self.run), 'Dia_channel_screen_channels', 'even')
		print 'Done'

	def Modify_odd(self):
		print 'Modifying odd settings file...', ; sys.stdout.flush()
		Replace_Settings_Line(self.settings_dir + '/odd/settings.{r}.ini'.format(r=self.run), 'Dia_channel_screen_channels', 'odd')
		print 'Done'

	def CheckStripTelescopeAnalysis(self):
		if os.path.isdir(self.StripTelescopeAnalysis_path):
			if not os.path.isfile(self.StripTelescopeAnalysis_path + '/diamondAnalysis'):
				ExitMessage('{p}/diamondAnalysis does not exist. Exiting'.format(p=self.StripTelescopeAnalysis_path))
		else:
			ExitMessage('{d} does not exist. Exiting'.format(d=self.StripTelescopeAnalysis_path))

	def First_Analysis(self):
		self.subdir = 'no_mask'
		if self.delete_old:
			self.Delete_old()
		print 'Starting first analysis (no_mask)...'
		self.RunAnalysis()
		print 'Finished with first analysis :)'

	def RunAnalysis(self):
		CreateDirectoryIfNecessary(self.out_dir + '/' + self.subdir + '/' + str(self.run))
		RecreateSoftLink(self.out_dir + '/' + self.subdir + '/' + str(self.run), self.scratch_path, str(self.run) + '_' + self.subdir, 'dir', False)
		self.Print_subprocess_command('{d}/{sd}/RunList_{r}.ini'.format(d=self.run_lists_dir, sd=self.subdir, r=self.run), self.settings_dir + '/' + self.subdir, self.out_dir + '/' + self.subdir, self.data_dir + '/' + str(self.run))
		if self.batch:
			self.sub_pro = subp.Popen(['{p}/diamondAnalysis'.format(p=self.StripTelescopeAnalysis_path), '-r', '{d}/{sd}/RunList_{r}.ini'.format(d=self.run_lists_dir, sd=self.subdir, r=self.run), '-s', self.settings_dir + '/' + self.subdir, '-o', self.out_dir + '/' + self.subdir, '-i', self.data_dir + '/' + str(self.run)], bufsize=-1, stdin=subp.PIPE, stdout=open('/dev/null', 'w'), close_fds=True)
		else:
			self.sub_pro = subp.Popen(['{p}/diamondAnalysis'.format(p=self.StripTelescopeAnalysis_path), '-r', '{d}/{sd}/RunList_{r}.ini'.format(d=self.run_lists_dir, sd=self.subdir, r=self.run), '-s', self.settings_dir + '/' + self.subdir, '-o', self.out_dir + '/' + self.subdir, '-i', self.data_dir + '/' + str(self.run)], bufsize=-1, stdin=subp.PIPE, close_fds=True)
		while self.sub_pro.poll() is None:
			pass
		if self.sub_pro.poll() == 0:
			print 'Run finished successfully'
		else:
			print 'Run could have failed. Obtained return code:', self.sub_pro.poll()
		CloseSubprocess(self.sub_pro, True, False)

		if self.do_odd:
			CreateDirectoryIfNecessary(self.out_dir + '/' + self.subdir + '/odd/' + str(self.run))
			self.LinkRootFiles(self.out_dir + '/' + self.subdir + '/' + str(self.run), self.out_dir + '/' + self.subdir + '/odd/' + str(self.run), upto='cluster', doCopy=True)
			self.Print_subprocess_command('{d}/{sd}/odd/RunList_{r}.ini'.format(d=self.run_lists_dir, sd=self.subdir, r=self.run), self.settings_dir + '/' + self.subdir + '/odd', self.out_dir + '/' + self.subdir + '/odd', self.data_dir + '/' + str(self.run))
			self.sub_pro_o = subp.Popen(['{p}/diamondAnalysis'.format(p=self.StripTelescopeAnalysis_path), '-r', '{d}/{sd}/odd/RunList_{r}.ini'.format(d=self.run_lists_dir, sd=self.subdir, r=self.run), '-s', self.settings_dir + '/' + self.subdir + '/odd', '-o', self.out_dir + '/' + self.subdir + '/odd', '-i', self.data_dir + '/' + str(self.run)], bufsize=-1, stdin=subp.PIPE, stdout=open('/dev/null', 'w'), close_fds=True)
		if self.do_even:
			CreateDirectoryIfNecessary(self.out_dir + '/' + self.subdir + '/even/' + str(self.run))
			self.Print_subprocess_command('{d}/{sd}/even/RunList_{r}.ini'.format(d=self.run_lists_dir, sd=self.subdir, r=self.run), self.settings_dir + '/' + self.subdir + '/even', self.out_dir + '/' + self.subdir + '/even', self.data_dir + '/' + str(self.run))
			self.sub_pro_e = subp.Popen(['{p}/diamondAnalysis'.format(p=self.StripTelescopeAnalysis_path), '-r', '{d}/{sd}/even/RunList_{r}.ini'.format(d=self.run_lists_dir, sd=self.subdir, r=self.run), '-s', self.settings_dir + '/' + self.subdir + '/even', '-o', self.out_dir + '/' + self.subdir + '/even', '-i', self.data_dir + '/' + str(self.run)], bufsize=-1, stdin=subp.PIPE, stdout=open('/dev/null', 'w'), close_fds=True)
		if self.do_odd:
			while self.sub_pro_o.poll() is None:
				pass
			if self.sub_pro_o.poll() == 0:
				print 'Run odd finished'
			else:
				print 'Run odd could have failed. Obtained return code:', self.sub_pro_o.poll()
			CloseSubprocess(self.sub_pro_o, True, False)
		if self.do_even:
			while self.sub_pro_e.poll() is None:
				pass
			if self.sub_pro_e.poll() == 0:
				print 'Run even finished'
			else:
				print 'Run even could have failed. Obtained return code:', self.sub_pro_e.poll()
			CloseSubprocess(self.sub_pro_e, True, False)

	def Print_subprocess_command(self, runlist, setting, outdir, inputdir):
		print 'Executing:\n{p}/diamondAnalysis -r {r} -s {s} -o {o} -i {i}\n'.format(p=self.StripTelescopeAnalysis_path, r=runlist, s=setting, o=outdir, i=inputdir)

	def LinkRootFiles(self, source, dest, upto='selection', doSymlink=True, doCopy=True, nodir=False):
		steps = ['raw', 'pedestal', 'cluster', 'selection', 'align', 'transparent', '3d']
		cumulative = []
		for elem in steps:
			cumulative.append(elem)
			if elem == upto:
				break
		successful = True
		if 'raw' in cumulative:
			if not os.path.isfile(dest + '/rawData.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/rawData.{r}.root'.format(r=self.run), dest, 'rawData.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
		if 'pedestal' in cumulative:
			if not os.path.isfile(dest + '/pedestalData.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/pedestalData.{r}.root'.format(r=self.run), dest, 'pedestalData.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
				if not nodir: RecreateLink(source + '/pedestalAnalysis', dest, 'pedestalAnalysis', doSymlink, doCopy)
		if 'cluster' in cumulative:
			if not os.path.isfile(dest + '/clusterData.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/clusterData.{r}.root'.format(r=self.run), dest, 'clusterData.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
				if not nodir: RecreateLink(source + '/clustering', dest, 'clustering', doSymlink, doCopy)
			if not os.path.isfile(dest + '/etaCorrection.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/etaCorrection.{r}.root'.format(r=self.run), dest, 'etaCorrection.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
			if os.path.isfile(source + '/crossTalkCorrectionFactors.{r}.txt'.format(r=self.run)) and doCopy:
				shutil.copy(source + '/crossTalkCorrectionFactors.{r}.txt'.format(r=self.run), dest + '/')
		if 'selection' in cumulative:
			if not os.path.isfile(dest + '/selectionData.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/selectionData.{r}.root'.format(r=self.run), dest, 'selectionData.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
				if not nodir: RecreateLink(source + '/selectionAnalysis', dest, 'selectionAnalysis', doSymlink, doCopy)
				if not nodir: RecreateLink(source + '/selections', dest, 'selections', doSymlink, doCopy)
		if 'align' in cumulative:
			if not os.path.isfile(dest + '/alignment.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/alignment.{r}.root'.format(r=self.run), dest, 'alignment.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
				if not nodir: RecreateLink(source + '/alignment', dest, 'alignment', doSymlink, doCopy)
		if 'transparent' in cumulative:
			if not os.path.isfile(dest + '/transparentAnalysis'):
				if not nodir:
					successful2 = RecreateLink(source + '/transparentAnalysis', dest, 'transparentAnalysis', doSymlink, doCopy)
					successful = successful and successful2
		if '3d' in cumulative:
			if not os.path.isfile(dest + '/analysis3d.root.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/analysis3d.root.{r}.root'.format(r=self.run), dest, 'analysis3d.root.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
			if not os.path.isfile(dest + '/analysis3d-2.root.{r}.root'.format(r=self.run)):
				successful2 = RecreateLink(source + '/analysis3d-2.root.{r}.root'.format(r=self.run), dest, 'analysis3d-2.root.{r}.root'.format(r=self.run), doSymlink, doCopy)
				successful = successful and successful2
			if not os.path.isfile(dest + '/3dDiamondAnalysis'):
				if not nodir:
					successful2 = RecreateLink(source + '/3dDiamondAnalysis', dest, '3dDiamondAnalysis', doSymlink, doCopy)
					successful = successful and successful2

		if os.path.isfile(source + '/index.php'):
			shutil.copyfile(source + '/index.php', dest + '/index.php')
		if os.path.isfile(source + '/overview.html'):
			shutil.copyfile(source + '/overview.html', dest + '/overview.html')
		if os.path.isfile(source + '/results_{r}.res'.format(r=self.run)) and doCopy:
			shutil.copyfile(source + '/results_{r}.res'.format(r=self.run), dest + '/results_{r}.res'.format(r=self.run))
		if os.path.isfile(source + '/results_{r}.txt'.format(r=self.run)) and doCopy:
			shutil.copyfile(source + '/results_{r}.txt'.format(r=self.run), dest + '/results_{r}.txt'.format(r=self.run))
		if not os.path.isfile(dest + '/Results.{r}.root'.format(r=self.run)):
			RecreateLink(source + '/Results.{r}.root'.format(r=self.run), dest, 'Results.{r}.root'.format(r=self.run), doSymlink, doCopy)
		return successful

	def Normal_Analysis(self):
		if self.delete_old:
			self.Delete_old()
		if os.path.isfile(self.out_dir + '/' + self.subdir + '/' + str(self.run) + '/rawData.{r}.root'.format(r=self.run)):
			if self.Get_num_events(self.out_dir + '/' + self.subdir + '/' + str(self.run) + '/rawData.{r}.root'.format(r=self.run), 'rawTree') < self.num_events:
				print 'Rerunning first event (no_mask) as it has less entries than required...'
				self.subdir = 'no_mask'
				self.num_events = self.total_events
				self.Create_Run_List()
				self.Check_settings_file()
				self.First_Analysis()
			elif self.Get_num_events(self.out_dir + '/' + self.subdir + '/' + str(self.run) + '/rawData.{r}.root'.format(r=self.run), 'rawTree') > self.num_events:
				print 'Need to recreate the rawTree'
				self.ExtractFromOriginalRawTree('no_mask')
		elif os.path.isfile(self.out_dir + '/no_mask/{r}/rawData.{r}.root'.format(r=self.run)):
			if self.Get_num_events(self.out_dir + '/no_mask/{r}/rawData.{r}.root'.format(r=self.run), 'rawTree') > self.num_events:
				print 'Extracting', self.num_events, 'events from no_mask run'
				self.ExtractFromOriginalRawTree('no_mask')
			else:
				if self.Get_num_events(self.out_dir + '/no_mask/{r}/rawData.{r}.root'.format(r=self.run), 'rawTree') < self.num_events:
					print 'The no_mask raw file has', self.Get_num_events(self.out_dir + '/no_mask/{r}/rawData.{r}.root'.format(r=self.run), 'rawTree'), 'events which is less than the requested. Will analyse all events'
					self.num_events = self.Get_num_events(self.out_dir + '/no_mask/{r}/rawData.{r}.root'.format(r=self.run), 'rawTree')
				self.LinkRootFiles(self.out_dir + '/no_mask', self.out_dir + '/' + self.subdir, 'raw', True, True)
		self.RunAnalysis()
		print 'Finished :)'

	def Delete_old(self, upto='3d'):
		print 'Deleting old upto', upto, ; sys.stdout.flush()
		steps = ['raw', 'pedestal', 'cluster', 'selection', 'align', 'transparent', '3d']
		cumulative = []
		for elem in steps:
			cumulative.append(elem)
			if elem == upto:
				break
		stem_dir = '{od}/{sd}/{r}'.format(od=self.out_dir, sd=self.subdir, r=self.run)
		if 'raw' in cumulative:
			if os.path.isfile('{sd}/rawData.{r}.root'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/rawData.{r}.root'.format(sd=stem_dir, r=self.run))
		if 'pedestal' in cumulative:
			if os.path.isfile('{sd}/pedestalData.{r}.root'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/pedestalData.{r}.root'.format(sd=stem_dir, r=self.run))
			if os.path.islink('{sd}/pedestalAnalysis'.format(sd=stem_dir)):
				os.unlink('{sd}/pedestalAnalysis'.format(sd=stem_dir))
			elif os.path.isdir('{sd}/pedestalAnalysis'.format(sd=stem_dir)):
				shutil.rmtree('{sd}/pedestalAnalysis'.format(sd=stem_dir))
		if 'cluster' in cumulative:
			if os.path.isfile('{sd}/clusterData.{r}.root'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/clusterData.{r}.root'.format(sd=stem_dir, r=self.run))
			if os.path.isfile('{sd}/etaCorrection.{r}.root'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/etaCorrection.{r}.root'.format(sd=stem_dir, r=self.run))
			if os.path.isfile('{sd}/crossTalkCorrectionFactors.{r}.txt'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/crossTalkCorrectionFactors.{r}.txt'.format(sd=stem_dir, r=self.run))
			if os.path.islink('{sd}/clustering'.format(sd=stem_dir)):
				os.unlink('{sd}/clustering'.format(sd=stem_dir))
			elif os.path.isdir('{sd}/clustering'.format(sd=stem_dir)):
				shutil.rmtree('{sd}/clustering'.format(sd=stem_dir))
		if 'align' in cumulative:
			if os.path.isfile('{sd}/alignment.{r}.root'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/alignment.{r}.root'.format(sd=stem_dir, r=self.run))
			if os.path.islink('{sd}/alignment'.format(sd=stem_dir)):
				os.unlink('{sd}/alignment'.format(sd=stem_dir))
			elif os.path.isdir('{sd}/alignment'.format(sd=stem_dir)):
				shutil.rmtree('{sd}/alignment'.format(sd=stem_dir))
		if 'transparent' in cumulative:
			if os.path.islink('{sd}/transparentAnalysis'.format(sd=stem_dir)):
				os.unlink('{sd}/transparentAnalysis'.format(sd=stem_dir))
			elif os.path.isdir('{sd}/transparentAnalysis'.format(sd=stem_dir)):
				shutil.rmtree('{sd}/transparentAnalysis'.format(sd=stem_dir))
		if '3d' in cumulative:
			if os.path.isfile('{sd}/analysis3d.root.{r}.root'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/analysis3d.root.{r}.root'.format(sd=stem_dir, r=self.run))
			if os.path.isfile('{sd}/analysis3d-2.root.{r}.root'.format(sd=stem_dir, r=self.run)):
				os.unlink('{sd}/analysis3d-2.root.{r}.root'.format(sd=stem_dir, r=self.run))
			if os.path.islink('{sd}/3dDiamondAnalysis'.format(sd=stem_dir)):
				os.unlink('{sd}/3dDiamondAnalysis'.format(sd=stem_dir))
			elif os.path.isdir('{sd}/3dDiamondAnalysis'.format(sd=stem_dir)):
				shutil.rmtree('{sd}/3dDiamondAnalysis'.format(sd=stem_dir))
		print 'Done'

	def Get_num_events(self, rootfile, treename):
		tempf = ro.TFile(rootfile, 'READ')
		tempt = tempf.Get(treename)
		num_evts = tempt.GetEntries()
		tempf.Close()
		return num_evts

	def ExtractFromOriginalRawTree(self, originalsubdir='no_mask'):
		CreateDirectoryIfNecessary(self.out_dir + '/' + originalsubdir + '/{r}'.format(r=self.run))
		if os.path.isfile(self.out_dir + '/' + originalsubdir + '/{r}/rawData.{r}.root'.format(r=self.run)):
			tempf = ro.TFile(self.out_dir + '/' + originalsubdir + '/{r}/rawData.{r}.root'.format(r=self.run), 'READ')
			tempt = tempf.Get('rawTree')
			print 'Extracting only', self.num_events, 'events starting from', self.first_event, 'to analyse...', ; sys.stdout.flush()
			leng = tempt.Draw('>>evlist', 'abs(2*EventNumber-{eva}-2*{evi}+1)<=({eva}-1)'.format(evi=self.first_event, eva=self.num_events))
			while leng > tempt.GetEstimate():
				tempt.SetEstimate(leng)
				leng = tempt.Draw('>>evlist', 'abs(2*EventNumber-{eva}-2*{evi}+1)<=({eva}-1)'.format(evi=self.first_event, eva=self.num_events))
			evlist = ro.gDirectory.Get('evlist')
			tempt.SetEventList(evlist)
			tempnf = ro.TFile(self.out_dir + '/' + self.subdir + '/' + str(self.run) + '/rawData.{r}.root'.format(r=self.run), 'RECREATE')
			tempnt = tempt.CopyTree('')
			tempnt.Write()
			tempnf.Close()
			tempf.Close()
			print 'Done'
		else:
			ExitMessage('Cannot extract from ' + originalsubdir + ' as it does not exist. Runn first the analysis with sub directory: ' + originalsubdir)

	def GetIndividualChannelHitmap(self):
		print 'Starting channel occupancy plots...'
		cont = False
		CreateDirectoryIfNecessary(self.out_dir + '/{sd}/{r}/channel_sweep'.format(sd=self.subdir, r=self.run))
		for ch in xrange(diaChs):
			CreateDirectoryIfNecessary(self.out_dir + '/{sd}/{r}/channel_sweep/{c}'.format(sd=self.subdir, c=ch, r=self.run))
			CreateDirectoryIfNecessary(self.out_dir + '/{sd}/{r}/channel_sweep/{c}/{r}'.format(sd=self.subdir, c=ch, r=self.run))
			do_continue = self.LinkRootFiles(self.out_dir + '/'+self.subdir+'/' + str(self.run), self.out_dir + '/{sd}/{r}/channel_sweep/{c}/{r}'.format(sd=self.subdir, c=ch, r=self.run), 'cluster', doSymlink=True, doCopy=False, nodir=True)
			if not do_continue:
				ExitMessage('Cannot create symlinks. Exiting...')
			self.ModifySettingsOneChannel(ch, self.subdir)
		num_cores = mp.cpu_count()
		num_parrallel = 1 if num_cores < 4 else 2 if num_cores < 8 else 4 if num_cores < 16 else 8 if num_cores < 32 else 16
		num_jobs = diaChs / num_parrallel
		channel_runs = np.arange(diaChs).reshape([num_jobs, num_parrallel])
		for bat in xrange(channel_runs.shape[0]):
			procx = []
			for proc in xrange(channel_runs.shape[1]):
				print 'Getting channel:', channel_runs[bat, proc], '...'
				procx.append(subp.Popen(
					['diamondAnalysis', '-r', '{d}/{sd}/channels/RunList_{r}.ini'.format(sd=self.subdir, d=self.run_lists_dir, r=self.run), '-s', self.settings_dir + '/{sd}/channels/{c}'.format(sd=self.subdir, c=channel_runs[bat, proc]),
					 '-o', self.out_dir + '/{sd}/{r}/channel_sweep/{c}'.format(sd=self.subdir, c=channel_runs[bat, proc], r=self.run), '-i', self.data_dir], bufsize=-1, stdin=subp.PIPE,
					stdout=open('/dev/null', 'w'), stderr=subp.STDOUT, close_fds=True))
			for proc in xrange(channel_runs.shape[1]):
				while procx[proc].poll() is None:
					# procx[proc].stdout.
					continue
				CloseSubprocess(procx[proc], stdin=True, stdout=False)
				print 'Done with channel:', channel_runs[bat, proc], ':)'
			# for proc in xrange(channel_runs.shape[1]):
			# 	CloseSubprocess(procx[proc], stdin=True, stdout=False)
			# 	print 'Done with channel:', channel_runs[bat, proc], ':)'
			del procx

	def ModifySettingsOneChannel(self, ch=0, sub_dir='no_mask'):
		CreateDirectoryIfNecessary(self.settings_dir + '/{sd}/channels'.format(sd=sub_dir))
		CreateDirectoryIfNecessary(self.settings_dir + '/{sd}/channels/{c}'.format(sd=sub_dir, c=ch))
		with open(self.settings_dir + '/{sd}/settings.{r}.ini'.format(sd=sub_dir, r=self.run), 'r') as fin:
			with open(self.settings_dir + '/{sd}/channels/{c}/settings.{r}.ini'.format(sd=sub_dir, c=ch, r=self.run), 'w') as fch:
				for line in fin:
					if not line.startswith('Dia_channel_screen_channels'):
						fch.write(line)
					else:
						channel_str_new = self.ModifyStringOneChannel(ch)
						fch.write('Dia_channel_screen_channels = {' + channel_str_new + '}\n')

	def ModifyStringOneChannel(self, ch=0):
		if ch == 0:
			return '1-{d}'.format(d=diaChs - 1)
		elif ch == diaChs - 1:
			return '0-{d}'.format(d=diaChs - 2)
		else:
			return '0-{cp},{cn}-{d}'.format(cp=ch - 1, cn = ch + 1, d=diaChs - 1)

def main():
	parser = OptionParser()
	parser.add_option('-s', '--settings', dest='settings_f', type='string', help='Settings file containing the information on the run and the analysis to do (e.g. settings.ini)')
	parser.add_option('--first', dest='first', default=False, action='store_true', help='enables first analysis wich has everything un-masked')
	parser.add_option('--normal', dest='normal', default=False, action='store_true', help='enables normal analysis')
	parser.add_option('--singlechannel', dest='singlech', default=False, action='store_true', help='enables single channel study. Requires a preexiting first analysis')

	(options, args) = parser.parse_args()
	settings_f = str(options.settings_f)
	first_ana = bool(options.first)
	normal_ana = bool(options.normal)
	single_ch = bool(options.singlech)

	rd42 = CurrentsMonitor()
	rd42.ReadInputFile(settings_f)
	if first_ana:
		rd42.subdir = 'no_mask'
	rd42.Create_Run_List(do_single_ch=single_ch)
	rd42.Check_settings_file()
	rd42.CheckStripTelescopeAnalysis()

	if first_ana:
		print 'Starting first analysis (no_mask)...\n'
		rd42.First_Analysis()
	elif normal_ana:
		print 'Starting normal analysis...\n'
		rd42.Normal_Analysis()
	if single_ch:
		rd42.GetIndividualChannelHitmap()


if __name__ == '__main__':
	main()
