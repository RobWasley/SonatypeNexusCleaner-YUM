# SonatypeNexusCleaner-YUM
Yum Repository Cleaner

#                Sonatype Nexus - Old Package Remover
#                        (YUM Repositorys)

This script removes old unused packages from yum repositories by reading the yum repo XML and comparing the file names.  

The reason we have to use the repo XML is because Nexus only returns the full path and stripping RPM names out of file names is risky.    

This will stop the ability of a yum downgrade but frees space on Nexus.  

You will need to "Compact" any blob stores affected to regain space.  

# !!!! CAUTION !!!!  
# This script is destructive.  
# Use at your own risk  
 Author: RobWasley 25/09/2018
