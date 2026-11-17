`bangladesh_areas.json` contains the 495 division/district/upazila records from
the [Bangladesh Administrative Divisions dataset](https://github.com/open-admin-data/bangladesh-administrative-divisions)
(CC BY 4.0), plus six newer upazilas present in the [Bangladesh National
Portal's upazila directory](https://bangladesh.gov.bd/views/upazila-list/).
The extra rows are Mokamtala, Chandraganj, Bhully, Ruhia, Bangra and South
Gafargaon.

The rows match `areas` in `ctrx.backup`: division and district codes are two
digits, and upazila codes are three digits. Upazila records use `name` because
that is the field used by the existing backend and UI. The source's four-digit
upazila ID suffix is mapped to the final three digits; the six newer rows use
the first unused three-digit code within their district.
