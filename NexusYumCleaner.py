import xmltodict
import json
import urllib2
import gzip
import shutil
import requests
import os
from requests.auth import HTTPBasicAuth
from distutils.version import LooseVersion

###################################################################
#                Sonatype Nexus - Old Package Remover
#                        (YUM Repositorys)
###################################################################
#
# This script removes old unused packages from yum repositories
# by reading the yum repo XML and comparing the file names.
# 
# The reason we have to use the repo XML is because Nexus only 
# returns the full path and stripping RPM names out of file names
# is risky.
# 
# This will stop the ability of a yum downgrade but frees space 
# on Nexus.
# 
# You will need to "Compact" any blob stores affected to regain 
# space.
#
# !!!! CAUTION !!!!
# This script is destructive.
# Use at your own risk
#
# Author: RobWasley 25/09/2018
#
###################################################################

dryRun = False 
# True will do a lovely test run without killing everything.
# False will murder all of the RPMs that are not the latest verstion.

nexusurl = "https://nexus.robwasley.com/repository/"
# URL of the nexus server that needs old packages removed.

nexususer = "user"
nexuspass = "password"
# Admin credentials for nexus so we can delete packages from the YUM
# repo.

repolist = ["alpha","beta"]
# Names of the YUM repositories that need to be pruned.

def download(url,name):
    file = urllib2.urlopen(url)
    with open(name,'wb') as output:
        output.write(file.read())

def log_files(file,name):
    hs = open(file,"a")
    hs.write(name)
    hs.write("\n")
    hs.close() 

for repository in repolist:
    if dryRun:
        print "Performing dry run..."
    try:
        os.remove(repository+"-delete.txt")
        os.remove(repository+"-all.txt")
    except OSError:
        pass
    
    print "#########################################"
    print "Cleaning up " + repository
    print "#########################################"
    repositoryurl = nexusurl + repository + "/"
    repomd = "repomd.xml"
    repomdurl = repositoryurl + "repodata/repomd.xml"

    try:
        # Download main repo file
        print "Downloading Repo XML..."
        download(repomdurl,repomd)
        # Convert xml to dict
        with open(repomd) as f:
            repo = xmltodict.parse(str(f.read()))
        # Copy location of primary repo file (contains a list of all of the RPMs)
        for xml in repo['repomd']['data']:
            if xml['@type'] == "primary":
                primary = repositoryurl + xml['location']['@href']
                primarygz = xml['location']['@href'][9:]
                primaryxml = primarygz[:-3]
        # Download primary repo file (this is a Gunzip file)
        download(primary,primarygz)
        # Extract the xml file from the primary.xml.gz
        with gzip.open(primarygz, 'rb') as f_in:
            with open(primaryxml, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        # Convert xml into dict
        with open(primaryxml) as f:
            doc = xmltodict.parse(str(f.read()))

        os.remove(repomd)
        os.remove(primarygz)
        os.remove(primaryxml)

        # "temp" will store all of the packages
        # "deleteme" will contain only the packages that are going to be deleted
        temp = []
        deleteme = []
        print "Writing Packages to list..."
        for rpm in doc['metadata']['package']:
            rpmDict = {"name": rpm['name'],"location":rpm['location']['@href'], "ver":rpm['version']['@ver'], "rel":rpm['version']['@rel']}
            temp.append(rpmDict)

        maxLen = len(temp)-1
        temp.sort()
        # Compare the packages in the list.
        # Compare the current with the next and if they are the same name check
        # to see if one is later than the other.

        print "Comparing versions..." 
        i = 0
        while i < maxLen:
            log_files(repository+"-all.txt",temp[i]['location'])
            if temp[i]['name'] == temp[i+1]['name']: 
                if LooseVersion(temp[i]['ver']) < LooseVersion(temp[i+1]['ver']):
                    deleteme.append(temp[i]['location'])

                elif LooseVersion(temp[i]['ver']) == LooseVersion(temp[i+1]['ver']):
                    if LooseVersion(temp[i]['rel']) < LooseVersion(temp[i+1]['rel']):
                        deleteme.append(temp[i]['location'])
            i += 1
        # Now we need to get the ID of the package (asset) from nexus
        # by querying all of the packages in the repo and compairing the
        # path that nexus gives us VS the path from the repo listing

        idlist = []
        nexusapi = nexusurl + "service/rest/v1/assets"
        continuationToken = True

        # For some reason Nexus pages the responces so we have to pass a 
        # continuation token from one request to another.

        print "Querying the Nexus API..."
        while continuationToken:
            urlparams = {'repository':repository} 
            if continuationToken != True:
                urlparams.update({'continuationToken': continuationToken})

            r = requests.get(url = nexusapi, params = urlparams) 
            data = r.json() 

            continuationToken = data['continuationToken']

            for rpm in data['items']:
                if rpm['path'] in deleteme:
                    deletethis = {"path":rpm['path'],"id":rpm['id']}
                    idlist.append(deletethis)

        # Finally, for each ID in idlist we want to run a delete request
        # so we can remove the redundant files.
        # expected responce is 204
        print "Removing files..."
        if dryRun:
            print "Dont worry this is a dry run. No files"
            print "will be harmed!"
        if len(idlist) == 0:
            print "No files to delete..."
        for rpmid in idlist:
            deleteurl = nexusapi + "/" + rpmid['id']
            log_files(repository+"-delete.txt",rpmid['path'])
            print rpmid['path']
            #print deleteurl
            if not dryRun:
                r = requests.delete(deleteurl, auth=HTTPBasicAuth(nexususer, nexuspass))
                if r.status_code == 204:
                    print "Deleted! Status: %d" % (r.status_code)
                else:
                    print "Something went wrong! Status: %d" % (r.status_code)
    except:
        print "Repo XML not found?"
        print "Wrong Repo url or no XML to download. Skipping {}".format(repository)
        pass
    
    print "Complete."
