#!/bin/bash

path=$1
currentpath=${PWD}
cd $path

git config diff.renameLimit 999999 

#Extract and format commit files information
git log --reverse --name-status --pretty=format:"commit	%H	%ct	%ce" --find-renames > $currentpath/log.log
awk -F$'\t' -f $currentpath/log.awk $currentpath/log.log 

#Remove temp file
#rm log.log

git config --unset diff.renameLimit
