=========================
Source of the test images
=========================

------
OsiriX
------

Many of the images that are used by the integration tests of Orthanc
come from the OsiriX samples available at:
http://www.osirix-viewer.com/datasets/

WARNING: The datasets from OsiriX are exclusively available for
research and teaching! You are not authorized to redistribute or sell
them, or use them for commercial purposes.


----
GDCM
----

Some images were collected by the GDCM project. They can be downloaded
courtesy of Jean-Pierre Roux at the following URL:
http://www.creatis.insa-lyon.fr/~jpr/PUBLIC/gdcm/gdcmSampleData


-------------
Other sources
-------------

Other images were publicly posted by external contributors to the
Orthanc project, or were generated manually by the Orthanc team.



-------
Content
-------

Here is the source of each set of sample images:

- Brainix/* : From OsiriX, "BRAINIX".
- DummyCT.dcm : From Osirix, "KNIX" with PixelData removed.
- Issue16.dcm : From Chris Hafey on Google Code (AT VR's are not returned properly as JSON)
- Issue19.dcm : From Chris Hafey on Google Code (YBR_FULL are not decoded incorrectly)
- Issue22.dcm : From Emsy Chan on Google Code (Error decoding multi-frame instances)
- Issue32.dcm : From aceberg93 on Google Code (Cyrillic symbols)
- Knee/* : From OsiriX, "KNEE".
- Multiframe.dcm : From GDCM, "images_of_interest/PHILIPS_Integris_H-8-MONO2-Multiframe.dcm"
- Phenix/* : From OsiriX, "PHENIX".
- PrivateTags.dcm : From GDCM, "images_of_interest/494APG9K.dcm"
- PrivateMDNTags.dcm : From University Hospital of Liege
- ColorTestMalaterre.dcm : From Mathieu Malaterre, Debian bug #698417
