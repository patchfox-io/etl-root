# ETL
scripts that are intended to form the business-logic basis for ci/cd automation that pushes data into PatchFox. 

The scripts are written with the intention of POSTing data to the `data-service` by way of the `/data` endpoint. OpenAPI docs [here](https://gitlab.com/patchfox2/data-service/-/blob/main/src/main/resources/openapi.json?ref_type=heads).  


## About the purl spec and PatchFox

PatchFox uses the purl spec to refer to software packages - ie "dependencies" We also use the same to refer to the sources of said packages. 

The purl format looks like this:

```scheme:type/namespace/name@version?qualifiers#subpath```

"scheme" and "type" will always be "pkg" and "generic" respectively 
{ORGANIZATION} is the name assigned to the client deployment - ie - https://{ORGANIZATION}.patchfox.io

{DATASET} for now will always be "ALL". In future an organization will be able to have more than one dataset at the enterprise pricepoint

{DATASOURCE} is exactly what it sounds like - the name of the thing pumping data into the pipeline. Usually this is the name of a git repository

{COMMIT_BRANCH} is the git branch from which this data came

{COMMIT_HASH} is the git commit hash from which this data came

{COMMIT_DATETIME} is an ISO formatted datetime string indicating when the commit occured from which this data came

examples:
```pkg:generic/{ORGANIZATION}/{DATASET}@{DATASOURCE}?{COMMIT_BRANCH}/{COMMIT_HASH}/{COMMIT_DATETIME}/```

```pkg:generic/acme/ALL@grype?/main/d5dd8011d1a55038262533675eddb96d98c4b984/2022-05-13T22:00:56+00:00```


## how the scripts work 
`run.sh` orchestrates things. It expects the following parametersL 

* ORGANIZATION
    * The name of the "deployment" is also the name of the organization. The PatchFox deployment for any given client will be resourced as `https://{organization}.patchfox.io`. 

* DATASOURCE
    * The name of the git repository 

* DATAPATH
    * The file system path where the git repository can be found 

* API_TOKEN
    * The JWT Bearer token required to make an auth call to PatchFox servers.

* API_URL
    * The URL of the PatchFox deployment you want to send the event message to. Note that the root domain must be `patchfox.io` for the argument to be considered valid. 

and takes an optional parameter: 
* WITH_HISTORY ("True")
    * causes the scripts to create and POST event payloads for every git commit affecting every discovered build file. The default behavior is to create an event for only the current HEAD commit. 

`generate_csv.py` is called by `run.sh` to discover all known build file types in the provided DATAPATH filetree. The result is a csv file indicating where on the file system those are as well as some metadata. What is considered "recognized" is defined in `constants.py`. The list includes many common package systems. 

`engage.py` is then called and, for every record resultant from `generate_csv`, the appropriate logic is called to bundle three files together into a zip archive and POST it to PatchFox servers. 

Finally, `engage.py` will call a routine to clear out any files added to system `/tmp`. 

Note that the csv file created by `generate_csv.py` is presently serialized to the same directory as `run.sh` is in. It is assumed this logic will be run either manually or by a ephemeral cd/cd job and as such no orphaned artifacts on the file system should result from running these scripts. 


## what's the legacy folder 
The original form of these scripts - please leave it be. There for archival and referfence purposes. 

