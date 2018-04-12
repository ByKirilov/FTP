from ftplib import FTP

ftp = FTP('ftp.mccme.ru')
ftp.login()
print(ftp.dir())
ftp.retrlines('retr')
print("Done")
