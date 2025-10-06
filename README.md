

05/10

- Sharing entity_classification.py; Can be useful if you are able to observe the data (i.e. RIAs by FINRA/SEC); 

06/10
 
- Introduced a new classify_by_forms which is way more reliable than the ENTS class, especially when you have IDX data available
- It uses the classify_by_re (05/10 version) as fallback if the form types are 100% possible on both entity types (144,3,4,5,...)
- classify_by_forms also returns some regimes e.g. N-4 --> "is_insurance"
- Note to myself: Have to upload the IDXParser -- done, but support functions are missing -- not working for your device yet
