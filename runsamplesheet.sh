#!/bin/bash

if [ -z "$VIRTUAL_ENV" ]
then
    echo "Please activate a virtual environment"
    echo "Usually you do this as follows:"
    echo ". /path/to/bin/activate"
    exit 1
fi

# We actually want the full path to scripts
scripts=$(cd $(dirname $0) && pwd)

# Where are the read files at?
reads_by_sample=$1
if [ -z "$reads_by_sample" ]
then
    echo "Please give me the location to the directory that holds all reads by sample"
    exit 1
fi

# Where is the sample/reference mapping file that the user gave us
sample_ref_map_file=$2
if [ -z "$sample_ref_map_file" ]
then
    echo "Give me a file that is space delimited with samplename reference one per line"
    exit 1
fi

if [ ! -e ${scripts}/perms.sh ]
then
    echo "Please setup perms.sh first"
    echo "You can copy perms.sh-example to perms.sh and then modify it"
    exit 1
fi

# Call perms.sh to setup the permissions environment
bash ${scripts}/perms.sh

# Loop over each of our samplenames and references
# File needs to be either space or tab delimeted
# Samplename ReferencePath
# Excluding any lines that begin with a #
grep -v '^#' $sample_ref_map_file | while read sample reference
do
    # Make sure that sample was set
    if [ -z "${sample}" ]
    then
        echo "${sample_ref_map_file} must have an incorrect line. Could not read samplename"
        continue
    fi
    # Make sure that sample was set
    if [ -z "${reference}" ]
    then
        echo "${sample_ref_map_file} must have an incorrect line. Could not read reference"
        continue
    elif [ ! -f "${reference}" ]
    then
        echo "${reference} is not a file that can be read. Skipping ${sample}"
        continue
    fi
    # If the sample already has been run
    #  then don't rerun it
    if [ -d ${sample} ]
    then
        echo "Skipping ${sample} because it already exists"
        continue
    fi

    mkdir -p Projects && cd Projects
    ${scripts}/runsample.py ${reads_by_sample}/${sample} ${reference} ${sample} -od ${sample}
    ret=$?
    # Detect if bwa didn't run correctly
    if [ $ret -ne 0 ]
    then
        echo "runsample.py did not run successfully for ${sample}"
    fi
    cd ..
done