#! /bin/bash
set -e

#find setup.py
if [ -e setup.py ]; then
    filename=setup.py
elif [ -e shn_bin/setup.py ]; then
    filename=shn_bin/setup.py
else
    echo 'missing setup.py'
    exit 1
fi


#find the version line in setup.py:   version='1.2.3',
versionline=$(grep '^\s*version\s*=' ${filename}) || exit

#split versionline into array VLINEARR=(version, '1.2.3',)
IFS='=' read -r -a VLINEARR <<< "${versionline}"

#strip spaces for VLINEARR[1], if any
VLINEARR[1]=${VLINEARR[1]//[[:blank:]]/}

#check if VLINEARR[1] has camma
if [ ${VLINEARR[1]:$(expr ${#VLINEARR[1]} - 1)} == ',' ]; then
    has_camma=yes
else
    has_camma=no
fi

#strip quotation marks from VLINEARR[1]
if [ ${VLINEARR[1]:0:1} == "'" ]; then
    IFS="'" read -r -a VERSIONARR <<< "${VLINEARR[1]}"
elif [ ${VLINEARR[1]:0:1} == '"' ]; then
          IFS='"' read -r -a VERSIONARR <<< "${VLINEARR[1]}"
else
    echo "version setting is incorrect"
    exit 1
fi
olddigits=${VERSIONARR[1]}

#split the digits into digit array and bump up the last digit by 1
IFS='.' read -r -a DIGITARR <<< "${olddigits}"
DIGITARR[${#DIGITARR[@]}-1]=${BUILD_NUMBER}

#combine into a new version line
function join_by { local IFS="$1"; shift; echo "$*"; }
newdigits=$(join_by . "${DIGITARR[@]}")
newversionline="'"${newdigits}"'"
if [ ${has_camma} == 'yes' ]; then
    newversionline=${newversionline}","
fi
newversionline="${VLINEARR[0]} = ${newversionline}"

#replace inline the old version line by the new version line
sed -i -e "s:${versionline}:${newversionline}:g" ${filename}
cat ${filename}
