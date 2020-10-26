# Simple GUI for process_um_folder functions
# Allows converting acquisitions from Ultramicroscope to Big Stitcher projects
#
# License BSD-3
# Author:
# Volker.
# Hilsenstein@
# monash
# edu

from PyQt5 import QtWidgets, QtCore, QtGui
from um2bs.process_um_folder import um_mosaic_folder
from um2bs.background_worker import Worker, WorkerSignals
import pathlib

# To add progress bar https://riptutorial.com/pyqt5/example/29500/basic-pyqt-progress-bar
# to add a waiting spinner (while looking for wells) https://gist.github.com/eyllanesc/1a09157d17ba13d223c312b28a81c320
# don't block main event loop: https://www.learnpyqt.com/courses/concurrent-execution/multithreading-pyqt-applications-qthreadpool/


class UltraMicroscopeToBigStitcherGUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(UltraMicroscopeToBigStitcherGUI, self).__init__(parent)
        self.processor = None
        self.rootfolder = "C:/Users/Volker/Data/Ultra_Oct2019/ultra_microscope_minimal"
        self.outfolder = ""
        self.threadpool = QtCore.QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

        self.layout = QtWidgets.QVBoxLayout()

        # folders
        self.inputFolderButton = QtWidgets.QPushButton("Select input folder")
        self.selectedroot = QtWidgets.QLabel(self.rootfolder)
        self.outputFolderButton = QtWidgets.QPushButton("Select output folder")
        self.selectedoutput = QtWidgets.QLabel(self.outfolder)
        # nr of files found info
        self.nr_files_found = QtWidgets.QLabel("input folder not scanned yet")
        # output option checkboxes
        self.checkbox_2D = QtWidgets.QCheckBox("create 2D BDV file (max-projected Z)")
        self.checkbox_2D.setChecked(True)
        self.checkbox_3D = QtWidgets.QCheckBox("create 3D BDV file")
        self.checkbox_3D.setChecked(False)
        # regular expressions for file selection and metadata extraction
        self.lineedit_re_filewhitelist = QtWidgets.QLineEdit()
        self.lineedit_re_filewhitelist.setText(".*tif")
        self.lineedit_re_Z = QtWidgets.QLineEdit()
        self.lineedit_re_Z.setText("(?<=_C)\d+")  # https://regex101.com/r/lQfpkm/1/
        self.lineedit_re_ch = QtWidgets.QLineEdit()
        self.lineedit_re_ch.setText("(?<=channel)\d+")
        self.lineedit_re_illu = QtWidgets.QLineEdit()
        self.lineedit_re_illu.setText(
            "(?<=_Ill)[\da-zA-Z]+"
        )  # https://regex101.com/r/sk8w3u/1/

        # voxel dimensions
        self.lineedit_zspacing = QtWidgets.QLineEdit()
        self.lineedit_zspacing.setText("1.00")
        self.lineedit_zspacing.setValidator(QtGui.QDoubleValidator(0.0, 10000.0, 2))
        self.lineedit_xyspacing = QtWidgets.QLineEdit()
        self.lineedit_xyspacing.setText("1.00")
        self.lineedit_xyspacing.setValidator(QtGui.QDoubleValidator(0.0, 10000.0, 2))
        # List of tiles
        self.listWidget = QtWidgets.QListWidget()
        self.listWidget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.listWidget.setGeometry(QtCore.QRect(10, 10, 211, 291))
        self.startProcessingButton = QtWidgets.QPushButton("Process selected folders")
        self.startProcessingButton.setEnabled(False)
        # Make connections
        self.listWidget.itemSelectionChanged.connect(self._checkProcessingButton)
        self.inputFolderButton.clicked.connect(self.get_root_folder)
        self.outputFolderButton.clicked.connect(self.get_output_folder)
        self.startProcessingButton.clicked.connect(self.process)
        # Assemble GUI elements into final layout

        self.layout.addWidget(self.inputFolderButton)
        self.layout.addWidget(QtWidgets.QLabel("Input folder:"))
        self.layout.addWidget(self.selectedroot)
        self.layout.addWidget(
            QtWidgets.QLabel("Regular expression for files to consider")
        )
        self.layout.addWidget(self.lineedit_re_filewhitelist)
        self.layout.addWidget(self.nr_files_found)
        self.layout.addWidget(self.outputFolderButton)
        self.layout.addWidget(QtWidgets.QLabel("Output folder:"))
        self.layout.addWidget(self.selectedoutput)

        self.layout.addWidget(QtWidgets.QLabel("Regular expression for Z slices <zpos>"))
        self.layout.addWidget(self.lineedit_re_Z)
        self.layout.addWidget(QtWidgets.QLabel("Regular expression for channels <ch>"))
        self.layout.addWidget(self.lineedit_re_ch)
        self.layout.addWidget(
            QtWidgets.QLabel("Regular expression for illumination <illu>")
        )
        self.layout.addWidget(self.lineedit_re_illu)
        self.layout.addWidget(self.checkbox_2D)
        self.layout.addWidget(self.checkbox_3D)
        self.layout.addWidget(QtWidgets.QLabel("Enter XY spacing in um/voxel:"))
        self.layout.addWidget(self.lineedit_xyspacing)
        self.layout.addWidget(QtWidgets.QLabel("Enter Z spacing in um/voxel:"))
        self.layout.addWidget(self.lineedit_zspacing)

        # self.layout.addWidget(QtWidgets.QLabel("Select the wells to process:"))
        # self.layout.addWidget(self.listWidget)
        self.layout.addWidget(self.startProcessingButton)

        self.setLayout(self.layout)

    def get_root_folder(self):
        self.rootfolder = str(
            QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory")
        )
        self.update_files()
        self._trigger_update()

    def get_output_folder(self):
        self.outfolder = str(
            QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder")
        )
        self.selectedoutput.setText(self.outfolder)
        self._checkProcessingButton()

    def process(self):
        self.startProcessingButton.setEnabled(False)

        worker = Worker(self._process)
        worker.signals.finished.connect(self._checkProcessingButton)
        self.threadpool.start(worker)

    def _process(self, *args, **kwargs):

        print(f"Input folder {self.rootfolder}")
        print(f"Output folder {self.outfolder}")
        print(f"2D projection {self.checkbox_2D.isChecked()}")
        print(f"2D volume {self.checkbox_3D.isChecked()}")
        print(f"xy scale um/pix {float(self.lineedit_xyspacing.text())}")
        print(f"z scale um/pix {float(self.lineedit_zspacing.text())}")

        self.processor.generate_big_stitcher(
            outfolder_base=self.outfolder,
            projected=self.checkbox_2D.isChecked(),
            volume=self.checkbox_3D.isChecked(),
            xyspacing=float(self.lineedit_xyspacing.text()),
            zspacing=float(self.lineedit_zspacing.text()),
        )

    def _checkProcessingButton(self):
        # if (
        #    self.listWidget.count() > 0
        #    and self.outfolder != ""
        #    and len(self._get_selected_indices()) > 0
        # ):
        if self.outfolder != "" and self.rootfolder != "":
            self.startProcessingButton.setEnabled(True)
        else:
            self.startProcessingButton.setEnabled(False)

    def _trigger_update(self):
        worker = Worker(self.update_files)
        # worker.signals.result.connect(self.print_output)
        worker.signals.finished.connect(self._checkProcessingButton)
        # worker.signals.progress.connect(self.progress_fn)
        print("starting worker to find files")
        self.threadpool.start(worker)

    def update_files(self, *args, **kwargs):
        print("in update wells")
        self.selectedroot.setText(self.rootfolder)
        # self.listWidget.clear()
        print("initializing Matrix processor")
        res = {}
        for re_name in ["filewhitelist", "Z", "ch", "illu"]:
            widget = eval(f"self.lineedit_re_{re_name}")
            res[re_name] = widget.text()
        self.nr_files_found.setText("Looking for files ...")
        self.processor = um_mosaic_folder(self.rootfolder, res)

        print(self.processor.df)
        self.nr_files_found.setText(f"{len(self.processor.df)} files found")

def run():
    import sys

    app = QtWidgets.QApplication(sys.argv)
    form = UltraMicroscopeToBigStitcherGUI()
    form.show()
    app.exec_()


if __name__ == "__main__":
    run()