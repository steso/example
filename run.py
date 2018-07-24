#!/usr/bin/env python3
import argparse
import os
import nibabel as nib
import numpy as np
from glob import glob
from diffqc import *

__version__ = open(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                'version')).read()

parser = argparse.ArgumentParser(description='Example BIDS App entrypoint script.')
parser.add_argument('bids_dir', help='The directory with the input dataset '
                    'formatted according to the BIDS standard.')
parser.add_argument('output_dir', help='The directory where the output files '
                    'should be stored. If you are running group level analysis '
                    'this folder should be prepopulated with the results of the'
                    'participant level analysis.')
parser.add_argument('analysis_level', help='Level of the analysis that will be performed. '
                    'Multiple participant level analyses can be run independently '
                    '(in parallel) using the same output_dir.',
                    choices=['participant', 'group'])
parser.add_argument('--participant_label', help='The label(s) of the participant(s) that should be analyzed. The label '
                   'corresponds to sub-<participant_label> from the BIDS spec '
                   '(so it does not include "sub-"). If this parameter is not '
                   'provided all subjects should be analyzed. Multiple '
                   'participants can be specified with a space separated list.',
                   nargs="+")
parser.add_argument('--skip_bids_validator', help='Whether or not to perform BIDS dataset validation',
                   action='store_true')
parser.add_argument('-v', '--version', action='version',
                    version='BIDS-App example version {}'.format(__version__))


args = parser.parse_args()

if not args.skip_bids_validator:
    helper.run('bids-validator %s'%args.bids_dir)

subjects_to_analyze = []
# only for a subset of subjects
if args.participant_label:
    subjects_to_analyze = args.participant_label
# for all subjects
else:
    subject_dirs = glob(os.path.join(args.bids_dir, "sub-*"))
    subjects_to_analyze = [subject_dir.split("-")[-1] for subject_dir in subject_dirs]

# running participant level
if args.analysis_level == "participant":
    # find all DWI files and run denoising and tensor / residual calculation
    for subject_label in subjects_to_analyze:





        print("processing sub-" + subject_label + "\n")

        # loop over DWI-Files
        for dwi_file in glob(os.path.join(args.bids_dir, "sub-%s"%subject_label,
                                          "dwi", "*_dwi.nii*")) + glob(os.path.join(args.bids_dir,"sub-%s"%subject_label,"ses-*","dwi", "*_dwi.nii*")):

            # create subj dir in qc_data & qc_figures folders
            subject_dir = os.path.join(args.output_dir, 'qc_data', 'sub-' + subject_label)
            fig_dir = os.path.join(args.output_dir, 'qc_figures', 'sub-' + subject_label)

            # check session
            if dwi_file.split("ses-")[-1] != dwi_file:
                ses = 'ses-' + dwi_file.split("ses-")[-1].split("_")[0]
                subject_dir = subject_dir + '_' + ses
                fig_dir = fig_dir + '_' + ses
            # check acquisition
            if dwi_file.split("acq-")[-1] != dwi_file:
                acq = 'acq-' + dwi_file.split("acq-")[-1].split("_")[0]
                subject_dir = subject_dir + '_' + acq
                fig_dir = fig_dir + '_' + acq

            # create output folder
            if not os.path.isdir(subject_dir):
                os.makedirs(subject_dir)
            if not os.path.isdir(fig_dir):
                os.makedirs(fig_dir)

            # add acquisition directory
            dwi = {}
            dwi['subject_label'] = subject_label
            dwi['fig_dir'] = fig_dir
            dwi['data_dir'] = subject_dir
            dwi['file'] = dwi_file
            dwi['bval'] = dwi['file'].replace("_dwi.nii.gz", "_dwi.bval")
            dwi['bvec'] = dwi['file'].replace("_dwi.nii.gz", "_dwi.bvec")

            # Get Header and flip_sign
            img = nib.load(dwi['file'])
            (M, perm, flip_sign) = helper.fixImageHeader(img)
            
            dwi['M'] = M
            dwi['perm'] = perm
            dwi['flip_sign'] = flip_sign

            # Get DWI sampling scheme
            participant.samplingScheme(dwi)

            # get nr of shells and directions
            participant.getShells(dwi)



            # Denoising to obtain noise-map
            participant.denoise(dwi)

            # # Step 2: Gibbs ringing removal (if available)
            # if unring_cmd:
            #     run.command(unring_cmd + ' dwi_denoised.nii dwi_unring' + fsl_suffix + ' -n 100')
            #     file.delTemporary('dwi_denoised.nii')
            #     unring_output_path = fsl.findImage('dwi_unring')
            #     run.command('mrconvert ' + unring_output_path + ' dwi_unring.mif -json_import input.json')
            #     file.delTemporary(unring_output_path)
            #     file.delTemporary('input.json')

            # b=0 and brain extraction
            participant.brainMask(dwi)


            numShells = sum(dwi['shells']>50) # use b<50 as b=0 images
            bShells = dwi['shells'][dwi['shells'] > 50]
            # MultiShell Datasets: perform tensor fit, residuals and fa per shell
            if numShells < 10 and numShells > 1:
                # backup MultiShell Files in Config
                origDWI = dwi.copy()

                for i in range(numShells):
                    bShell = bShells[i]
                    dwi['shellStr'] = "_b" + str(int(bShell))

                    dwi['data_dir'] = origDWI['data_dir'] + dwi['shellStr']
                    dwi['fig_dir'] = origDWI['fig_dir'] + dwi['shellStr']

                    # create output folder
                    if not os.path.isdir(dwi['data_dir']):
                        os.makedirs(dwi['data_dir'])
                    if not os.path.isdir(dwi['fig_dir']):
                        os.makedirs(dwi['fig_dir'])

                    dwi['denoised'] = origDWI['denoised'].replace(origDWI['data_dir'], dwi['data_dir'])
                    dwi['bval'] = dwi['denoised'].replace('.nii.gz', '.bval')
                    dwi['bvec'] = dwi['denoised'].replace('.nii.gz', '.bvec')

                    # extract shell from _denoise
                    cmd = "dwiextract -shells 0,%s -fslgrad %s %s -export_grad_fsl %s %s %s %s -force"%(str(int(bShell)),
                                                               origDWI['bvec'],
                                                               origDWI['bval'],
                                                               dwi['bvec'],
                                                               dwi['bval'],
                                                               origDWI['denoised'],
                                                               dwi['denoised'])
                    # print(cmd)
                    helper.run(cmd)

                    participant.getShells(dwi)

                    # perform tensor fit, faMap and Residuals
                    participant.dtiFit(dwi)
                    participant.faMap(dwi)
                    participant.tensorResiduals(dwi)


                # restore MultiShell Files in Config
                dwi = origDWI.copy()
            else:
                dwi['shellStr'] = ''
                # perform tensor fit
                participant.dtiFit(dwi)

                # Create FA maps
                participant.faMap(dwi)

                # Calc DTI residuals
                participant.tensorResiduals(dwi)

            # check DWI -> T1 overlay
            for t1_file in glob(os.path.join(args.bids_dir, "sub-%s"%subject_label,
                                              "anat", "*_T1w.nii*")) + glob(os.path.join(args.bids_dir,"sub-%s"%subject_label,"ses-*","anat", "*_T1w.nii*")):

                # check if T1 is from the correct session
                if dwi_file.split("ses-")[-1] != dwi_file:
                    ses = 'ses-' + dwi_file.split("ses-")[-1].split("_")[0]
                    ses_t1 = 'ses-' + t1_file.split("ses-")[-1].split("_")[0]
                    if ses != ses_t1:
                        # skip t1 file if sessions don't match!
                        t1_file = ''

                if (t1_file):
                    t1 = {}
                    t1['file'] = t1_file
                    participant.anatOverlay(dwi, t1)


# running group level
elif args.analysis_level == "group":

    # get figure names and number of figures per subject
    myList = []

    for subject_label in subjects_to_analyze:
        for image_file in glob(os.path.join(args.output_dir, 'qc_figures', "sub-%s*"%subject_label, "*.png")):
            myList.extend([os.path.basename(image_file)[0:-4]])

    imgSet = set(myList)

    wp = {}
    wp['filePath'] = os.path.join(args.output_dir, "_quality.html")
    wp['subjects'] = subjects_to_analyze
    wp['subFolders'] = [os.path.split(subF)[-1][4:] for subF in glob(os.path.join(args.output_dir,'qc_figures',"sub-*")) ]
    wp['figFolder'] = os.path.join(args.output_dir, 'qc_figures')
    wp['maxImg'] = len(imgSet)
    wp['maxList'] = list(sorted(imgSet))

    group.createWebPage(wp)
