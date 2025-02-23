import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import SpanSelector
import SpectrumPlotter
import ImagePlotter
import Image
import collections
import os
from mpl_toolkits.axes_grid1 import host_subplot
import matplotlib
matplotlib.use('TkAgg')

'''Things to do:
Add vertex addition and deletion after creation for patches
Why doesn't it work in multiple figures? --need to keep a reference to each one
Figure out changing contrast of extracted patch with spectrum spanselector
magic wand tool - auto-select regions of high intensity
'''

class SpectrumImagePlotter(object):
    def __init__(self, SI, filepath=os.getcwd(), cmap_im='gray'):
        '''Plot a 3D spectrum image array
        Input: 3D numpy array
        Optional argument: filepath to save spectra and images to
        Interactive commands on image axis: 
            enter: plot spectrum underneath current patch mask
            e: save image (not including contrast limits)
            n: start new polygon
            +: make new polygon group (for new spectrum)
            up, down arrow keys: move active polygon selection between groups
            left, right arrow keys: move active polygon selection to next polygon inside group
            m: provide handles on the vertices to adjust the polygon shape
        Interactive commands on spectrum axis:
            Click and drag over the spectrum to plot the slice in the image axis
            e: save spectrum as csv
        Interactive commands on contrast axis:
            Click and drag to select contrast range
        Interactive commands on extracted image axis:
            e: Save current patch to png'''
        self.filepath = filepath
        self.SI = SI
        if self.SI.spectrum_units is not None:
            self.spec_transform = (self.SI.spectrum_units, self.SI.secondary_units)
        else:
            self.spec_transform = None
        self.fig = plt.figure(figsize = (9,9), facecolor=[0.9, 0.9, 1])
        self.image_ax = plt.axes([0., 0.475, 0.45, 0.45])
        self.extracted_ax = plt.axes([0.45, 0.475, 0.45, 0.45])
        self.spectrum_ax = host_subplot(111)
        self.spectrum_ax.set_position([0.075, 0.07, 0.9, 0.35])
        self.spectrum_ax.patch.set_facecolor([0.9, 0.9, 1])
        self.contrast_ax = plt.axes([0.075, 0.925, 0.8, 0.075])
        self.colourbar_ax = plt.axes([0.9, 0.475, 0.05, 0.45]) 
        self.cmap = plt.get_cmap('Dark2')
        self.cmap_im = plt.get_cmap(cmap_im)
        # Spectrum axis plotting and interactive span
        self.extracted_mask = np.zeros(self.SI.size[:2]).astype(bool)
        mask3D = np.zeros(self.SI.size).astype(bool)
        self.extracted_spectrum = self.SI.ExtractSpectrum(mask3D)
        self.SpectrumPlot = SpectrumPlotter.SpectrumManager(
            self.extracted_spectrum, self.spectrum_ax, ax_transform = self.spec_transform, cmap=self.cmap)
        self.E_span = SpanSelector(self.spectrum_ax, self.SpectrumSpan, 'horizontal', 
            span_stays = True)
        self.Emin_i = 0
        self.Emax_i = len(self.extracted_spectrum.intensity)-1
        
        # Contrast histogram plotting and interactive span
        self.contrastbins = 256
        
        # Image axis plotting and interactive patches
        self.summedim = Image.Image(np.mean(self.SI.data[:, :, self.Emin_i:self.Emax_i], axis = 2))

        self.cmin = self.summedim.Imglim[0]
        self.cmax = self.summedim.Imglim[1]
        self.ImagePlot = ImagePlotter.ImagePlotter(self.summedim, 
            self.image_ax, 
            self.colourbar_ax,
            cmap = self.cmap_im,
            filepath=self.filepath,
            polygoncallback=self.ImageKeyCommands)
        self.PlotImage()
        self.PlotContrastHistogram()
        self.extractedim = Image.Image(np.ma.masked_array(self.summedim.data, np.invert(self.extracted_mask)))
        self.ExtractedImagePlot = collections.OrderedDict()
        self.PlotExtractedImage()
        self.connect()
    
    def connect(self):
        self.cidkey = self.image_ax.figure.canvas.mpl_connect('key_press_event', 
            self.keyboard_press)
    
    def keyboard_press(self, event):
        if event.inaxes == self.image_ax:
            self.ImageKeyCommands(event.key)
        elif event.inaxes == self.extracted_ax or event.inaxes == self.spectrum_ax:
            self.ExtractedImageKeyCommands(event.key)
    
    def ExtractedImageKeyCommands(self, key):
        if key == 'e':
            self.SaveSpectrumAndPatch() ## need to fix it so spectrum & patch come out with same name!
            ## Patches are no longer transparent when saving!
    
    def SaveSpectrumAndPatch(self):
        spectrumID = self.ImagePlot.PolygonGroups.currentID
        filename_spectrum = os.path.join(self.filepath, self.fig.canvas.get_window_title() + '_Spectrum_'+str(spectrumID)+'.csv')
        self.extracted_spectrum.SaveSpectrumAsCSV(filename_spectrum)
        filename_patch = os.path.join(self.filepath, self.fig.canvas.get_window_title() + '_Patch_'+str(spectrumID)+'.png')
        self.ExtractedImagePlot[self.ImagePlot.PolygonGroups.currentID].save_image(filename_patch)
    
    def ImageKeyCommands(self, key):
        if key == 'enter':
            MaskState = self.ImagePlot.PolygonGroups.ToggleActiveMask()
            if MaskState:
                mask = self.ImagePlot.PolygonGroups.GetActiveMask(self.summedim.size)
                mask3D = np.reshape(mask, 
                    (self.SI.size[0], self.SI.size[1], 1)) * np.ones((
                    self.SI.size[0], self.SI.size[1], self.SI.size[2])).astype(bool)
                mask_im = np.ma.masked_array(np.ones(np.shape(self.summedim.data))*mask.astype(int), np.invert(mask))
                self.extractedim = Image.Image(mask_im)
                self.AddExtractedImagePatch(self.ImagePlot.PolygonGroups.currentID)
                self.extracted_spectrum = self.SI.ExtractSpectrum(np.invert(mask3D))
                self.SpectrumPlot.update_spectrum(self.extracted_spectrum, 
                    self.ImagePlot.PolygonGroups.currentID)
                self.SpectrumPlot.make_visible(self.ImagePlot.PolygonGroups.currentID)
            else:
                self.SpectrumPlot.make_invisible(self.ImagePlot.PolygonGroups.currentID)
                self.RemoveExtractedImagePatch(self.ImagePlot.PolygonGroups.currentID)
        elif key == 'e':
            filename_addon = ('%.4g' % (self.SpectrumPlot.SpectrumPlot.spectrum.SpectrumRange[self.Emin_i])+'to'+
                '%.4g' % (self.SpectrumPlot.SpectrumPlot.spectrum.SpectrumRange[self.Emax_i])+
                self.SpectrumPlot.SpectrumPlot.spectrum.units)
            filename_image = (self.fig.canvas.get_window_title() + '_Image_' + filename_addon + '.png')
            filename_colourbar = (self.fig.canvas.get_window_title() + '_Colourbar_' + filename_addon + '.png')
            self.ImagePlot.save_image(os.path.join(self.filepath, filename_image))
            self.ImagePlot.save_colourbar(os.path.join(self.filepath, filename_colourbar))
        else:
            self.ImagePlot.image_key_commands(key)
    
    def PlotSpectrum(self):
        SpectrumPlot = SpectrumPlotter.SpectrumManager(
            self.extracted_spectrum, self.spectrum_ax, self.cmap)
        return SpectrumPlot
    
    def PlotContrastHistogram(self):
        if isinstance(self.summedim.data, np.ma.core.MaskedArray):
            self.summedimhist, self.summedimbins = np.histogram(self.summedim.data.compressed(), bins = self.contrastbins)
        else:
            self.summedimhist, self.summedimbins = np.histogram(self.summedim.data, bins = self.contrastbins)
        self.contrast_ax.cla()
        self.contrast_ax.plot(self.summedimbins[:-1], self.summedimhist, color = 'k')
        self.contrast_ax.set_axis_off()
        self.contrast_span = SpanSelector(self.contrast_ax, self.ContrastSpan, 'horizontal',
            span_stays = True, rectprops = dict(alpha = 0.5, facecolor = 'green'))
    
    def PlotImage(self):
        self.ImagePlot.RemoveImage()
        self.ImagePlot.ReplotImage(self.summedim, clim=[self.cmin, self.cmax])
        self.image_ax.set_axis_off()
    
    def PlotExtractedImage(self):
        self.extracted_ax.cla()
        self.extracted_ax.set_axis_off()
        self.ExtractedImagePlot[self.ImagePlot.PolygonGroups.currentID] = ImagePlotter.ImagePlotter(self.summedim, self.extracted_ax, polygoncallback=self.ExtractedImageKeyCommands)
        self.ExtractedImagePlot[self.ImagePlot.PolygonGroups.currentID].PlottedImage.set_alpha(0.1)
    
    def AddExtractedImagePatch(self, ID):
        self.ExtractedImagePlot[self.ImagePlot.PolygonGroups.currentID] = ImagePlotter.ImagePlotter(self.extractedim, self.extracted_ax, polygoncallback=self.ExtractedImageKeyCommands)
    
    def RemoveExtractedImagePatch(self, ID):
        self.ExtractedImagePlot[ID].PlottedImage.remove()
        pass
        
    def AdjustContrastExtractedImage(self):
        for (ID, image) in self.ExtractedImagePlot.items():
            image.PlottedImage.set_clim(vmin = self.cmin, vmax = self.cmax)

    def SpectrumSpan(self, Emin, Emax): ##Note: draws sub-pixel Espan, fix?
        Emin = np.max((np.round(Emin/self.SI.dispersion) * self.SI.dispersion, 
            self.SI.SpectrumRange[0]))
        Emax = np.min((np.round(Emax/self.SI.dispersion) * self.SI.dispersion, 
            self.SI.SpectrumRange[-1]))
        self.Emin_i = np.where(self.SpectrumPlot.SpectrumPlot.spectrum.SpectrumRange == Emin)[0]
        self.Emax_i = np.where(self.SpectrumPlot.SpectrumPlot.spectrum.SpectrumRange == Emax)[0]
        self.Emin_i = np.searchsorted(self.SpectrumPlot.SpectrumPlot.spectrum.SpectrumRange, Emin)
        self.Emax_i = np.searchsorted(self.SpectrumPlot.SpectrumPlot.spectrum.SpectrumRange, Emax)
        self.summedim = Image.Image(np.mean(self.SI.data[:, :, self.Emin_i:self.Emax_i], axis = 2))
        self.cmin = self.summedim.Imglim[0]
        self.cmax = self.summedim.Imglim[1]
        self.PlotImage()
        self.PlotContrastHistogram()
        
    def ContrastSpan(self, cmin, cmax):
        self.cmin = np.max((cmin, self.ImagePlot.Image.Imglim[0]))
        self.cmax = np.min((cmax, self.ImagePlot.Image.Imglim[1]))
        self.PlotImage()

    def ShowPlot(self):
        plt.show()
