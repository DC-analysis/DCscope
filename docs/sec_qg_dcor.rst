.. _sec_qg_dcor:

===================
Accessing DCOR data
===================

The `deformability cytometry open repository (DCOR)
<https://dcor.mpl.mpg.de>`_ allows you to upload and access RT-DC
datasets online (internet connection required). In DCscope, you
can access parts of the dataset (e.g. just two features) without
downloading the entire data file (which includes image, contour, and
traces information). This saves disk space and time when accessing
large datasets. For more information on how DCOR data are accessed,
please see the :ref:`dclab documentation <dclab:sec_av_dcor>`.

.. _qg_dcor_dlg:
.. figure:: scrots/qg_dcor_dlg.png
    :target: _images/qg_dcor_dlg.png

    Dialog for loading DCOR data.

In the *File* menu, choose *Load DCOR data*. A dialog 
(:numref:`qg_dcor_dlg`) lets you search data in the DCOR repository.

.. note::

    If you need to access :ref:`private data
    <dclab:sec_av_dcor_private_access>`, you have to specify your
    personal API key in the *DCOR* tab of the
    :ref:`preferences <sec_preferences>` (*Edit | Preferences*).
    There, you can also specify which server you wish to connect to.
    You can find your personal API Key in your user profile page after
    you logged in (e.g. at https://dcor.mpl.mpg.de, see also
    :ref:`dclab:sec_av_dcor_token`).

You can choose between a free text search (dataset and resource names,
tags, etc.) and an identifier search (dataset and resource identifiers).
After clicking the *Search* button, you may select the resources you
wish to load into your session in the list view below. Then, click
*Add to session* to load the data.


Encrypted access tokens
-----------------------
For some DCOR instances (e.g. self-hosted instances in your institute),
you might have received an encrypted access token (a *.dcor-access* file)
and a password. Click *Load an encrypted DCOR access token...* in the
*DCOR* tab of the preferences and enter the password. DCscope then
adds the server to the server list and stores the API key and the
server certificate contained in the access token.


.. _sec_qg_dcor_s3:

Basins in an S3 object store
----------------------------
Datasets may refer to :ref:`basins <dclab:sec_av_basins>` that are
stored in an :ref:`S3 object store <dclab:sec_av_s3>`. Public basins
are accessed without credentials. If the basins are
:ref:`private <dclab:sec_av_s3_private>`, you have to specify the
endpoint URL, the access key ID, and the secret access key in the
*S3 basins* tab of the preferences.
Please restart DCscope for these settings to take effect.
