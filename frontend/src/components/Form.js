import React, { useState } from 'react';
import { FormProvider, useForm, Controller } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from 'react-query';
import FormGroup from '@mui/material/FormGroup';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import InputLabel from '@mui/material/InputLabel';
import ConsentPersonal from './ConsentPersonal';
import ConsentTax from './ConsentTax';
import useAxios from '../utils/axiosHook';
import Box from '@mui/material/Box';
import { getDateWithYearOffset, isSINValid } from '../utility';
import LockIcon from '@mui/icons-material/Lock';
import InputAdornment from '@mui/material/InputAdornment';
import OutlinedInput from '@mui/material/OutlinedInput';
import Upload from './upload/Upload';
import Loading from './Loading';
import { useKeycloak } from '@react-keycloak/web';
import InfoTable from './InfoTable';
import { addTokenFields, checkBCSC } from '../keycloak';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import DateBoxes from './DateBoxes';

const maxDate = getDateWithYearOffset(new Date(), -16);
const minDate = getDateWithYearOffset(maxDate, -100);

export const defaultValues = {
  sin: '',
  first_name: '',
  last_name: '',
  middle_names: '',
  email: '',
  address: '',
  city: '',
  postal_code: '',
  date_of_birth: maxDate,
  drivers_licence: '',
  documents: [],
  consent_personal: false,
  consent_tax: false,
  application_type: 'individual'
};

const Form = ({ setNumberOfErrors, setErrorsExistCounter }) => {
  const [loading, setLoading] = useState(false);
  const [DOB, setDOB] = useState(maxDate);
  const queryClient = useQueryClient();
  const { keycloak } = useKeycloak();
  const kcToken = keycloak.tokenParsed;
  let bcscMissingFields = [];
  if (kcToken.identity_provider === 'bcsc') {
    bcscMissingFields = checkBCSC(kcToken);
  }
  const methods = useForm({
    defaultValues
  });
  const {
    control,
    handleSubmit,
    register,
    watch,
    formState: { errors },
    setValue
  } = methods;
  const axiosInstance = useAxios();
  const navigate = useNavigate();
  const mutation = useMutation((data) => {
    const formData = new FormData();
    for (const [key, value] of Object.entries(data)) {
      if (key === 'documents') {
        formData.append('doc1', value[0]);
        formData.append('doc2', value[1]);
      } else if (key === 'postal_code' && value.length === 7) {
        formData.append(key, value.replace(/[ -]/, ''));
      } else {
        formData.append(key, value);
      }
    }
    return axiosInstance.current.post('/api/application-form', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  });
  const onDobChange = (dob) => {
    setValue('date_of_birth', dob);
    setDOB(dob);
  };
  const onSubmit = (data) => {
    setNumberOfErrors(0);
    setLoading(true);
    if (kcToken.identity_provider !== 'bcsc') {
      data = {
        ...data,
        date_of_birth: data.date_of_birth.toISOString().slice(0, 10)
      };
    }
    mutation.mutate(data, {
      onSuccess: (data, variables, context) => {
        const id = data.data.id;
        let refinedData = data.data;
        if (kcToken.identity_provider === 'bcsc') {
          refinedData = addTokenFields(data.data, kcToken);
        }
        queryClient.setQueryData(['application', id], refinedData);
        navigate(`/details/${id}`);
      }
    });
  };

  const checkBackendAccessible = () => {
    const url = `/api/application-form/check_accessible`;
    return axiosInstance.current.get(url);
  };

  const checkDLStatus = (dl) => {
    const detailUrl = `/api/application-form/check_status/?drivers_license=${dl}`;
    return axiosInstance.current.get(detailUrl);
  };

  const onError = (errors) => {
    setLoading(false);
    const numberOfErrors = Object.keys(errors).length;
    setNumberOfErrors(numberOfErrors);
    if (numberOfErrors > 0) {
      setErrorsExistCounter((prev) => {
        return prev + 1;
      });
    }
  };

  return (
    <FormProvider {...methods}>
      <Loading open={loading} />
      <form onSubmit={handleSubmit(onSubmit, onError)}>
        <Box sx={{ display: 'inline' }}>
          <h3 id="form-submission-title">
            Your application information <LockIcon />
          </h3>
          <span> secure form submission</span>
          <p>
            The information you enter (name, date of birth, address and BC
            Driver's Licence number) must exactly match the ID you upload or
            your application will be declined.
          </p>
        </Box>
        {kcToken.identity_provider === 'bcsc' ? (
          <InfoTable kcToken={kcToken} bcscMissingFields={bcscMissingFields} />
        ) : (
          <>
            <FormGroup sx={{ mt: '20px' }}>
              {errors?.last_name?.type === 'required' && (
                <p className="error">Last Name cannot be blank</p>
              )}
              <InputLabel htmlFor="last_name" sx={{ color: 'black' }}>
                Your last name (surname):
              </InputLabel>
              <Controller
                name="last_name"
                control={control}
                render={({ field }) => (
                  <TextField
                    id="last_name"
                    inputProps={{ maxLength: 250 }}
                    onChange={(e) => setValue('last_name', e.target.value)}
                  />
                )}
                rules={{ required: true }}
              />
            </FormGroup>
            <FormGroup sx={{ mt: '20px' }}>
              {errors?.first_name?.type === 'required' && (
                <p className="error">First Name cannot be blank</p>
              )}
              <InputLabel htmlFor="first_name" sx={{ color: 'black' }}>
                First name (given name):
              </InputLabel>
              <Controller
                name="first_name"
                control={control}
                render={({ field }) => (
                  <TextField
                    id="first_name"
                    inputProps={{ maxLength: 250 }}
                    onChange={(e) => setValue('first_name', e.target.value)}
                  />
                )}
                rules={{ required: true }}
              />
            </FormGroup>
            <FormGroup sx={{ mt: '20px' }}>
              <InputLabel htmlFor="middle_names" sx={{ color: 'black' }}>
                Middle Names(s) (optional):
              </InputLabel>
              <Controller
                name="middle_names"
                control={control}
                render={({ field }) => (
                  <TextField
                    id="middle_names"
                    inputProps={{ maxLength: 250 }}
                    {...field}
                  />
                )}
              />
            </FormGroup>
            <FormGroup sx={{ mt: '20px' }}>
              <InputLabel htmlFor="date_of_birth" sx={{ color: 'black' }}>
                Date of birth:
              </InputLabel>
              <Controller
                name="date_of_birth"
                control={control}
                render={({ field }) => (
                  <LocalizationProvider dateAdapter={AdapterDateFns}>
                    <Box
                      sx={{
                        display: 'flex',
                        flexDirection: 'row',
                        paddingTop: '20px'
                      }}
                    >
                      <DateBoxes
                        maxDate={maxDate}
                        minDate={minDate}
                        value={DOB}
                        onChange={onDobChange}
                      />
                    </Box>
                  </LocalizationProvider>
                )}
              />
            </FormGroup>
            <FormGroup sx={{ mt: '20px' }}>
              {errors?.address?.type === 'required' && (
                <p className="error">Street Address cannot be blank</p>
              )}
              <InputLabel htmlFor="address" sx={{ color: 'black' }}>
                Street address:
              </InputLabel>
              <Controller
                name="address"
                control={control}
                render={({ field }) => (
                  <TextField
                    id="address"
                    inputProps={{ maxLength: 250 }}
                    onChange={(e) => setValue('address', e.target.value)}
                  />
                )}
                rules={{ required: true }}
              />
            </FormGroup>
            <FormGroup sx={{ mt: '20px' }}>
              {errors?.city?.type === 'required' && (
                <p className="error" sx={{ color: 'black' }}>
                  City cannot be blank
                </p>
              )}
              <InputLabel htmlFor="city" sx={{ color: 'black' }}>
                City:
              </InputLabel>
              <Controller
                name="city"
                control={control}
                render={({ field }) => (
                  <TextField
                    id="city"
                    inputProps={{ maxLength: 250 }}
                    onChange={(e) => setValue('city', e.target.value)}
                  />
                )}
                rules={{ required: true }}
              />
            </FormGroup>
            <FormGroup sx={{ mt: '20px' }}>
              {errors?.postal_code?.type === 'validate' && (
                <p className="error">Not a valid Postal Code</p>
              )}
              <InputLabel htmlFor="postal_code" sx={{ color: 'black' }}>
                Postal code (optional):
              </InputLabel>
              <Controller
                name="postal_code"
                control={control}
                render={({ field }) => (
                  <TextField
                    sx={{ width: '300px' }}
                    id="postal_code"
                    inputProps={{ maxLength: 7 }}
                    onChange={(e) => setValue('postal_code', e.target.value)}
                  />
                )}
                rules={{
                  validate: (inputtedPostalCode) => {
                    if (inputtedPostalCode) {
                      if (
                        inputtedPostalCode.length !== 6 &&
                        inputtedPostalCode.length !== 7
                      ) {
                        return false;
                      }
                      const regex = /[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d/;
                      if (!regex.test(inputtedPostalCode)) {
                        return false;
                      }
                    }
                    return true;
                  }
                }}
              />
            </FormGroup>
          </>
        )}
        <FormGroup sx={{ mt: '20px' }}>
          {errors?.email?.type === 'required' && (
            <p className="error">Email Address cannot be blank</p>
          )}
          <InputLabel htmlFor="email" sx={{ color: 'black' }}>
            Email Address:
          </InputLabel>
          <Controller
            name="email"
            type="email"
            control={control}
            render={({ field }) => (
              <TextField
                id="email"
                inputProps={{ maxLength: 250 }}
                onChange={(e) => setValue('email', e.target.value)}
              />
            )}
            rules={{ required: true }}
          />
        </FormGroup>
        <FormGroup sx={{ mt: '20px' }}>
          {errors?.sin?.type === 'validate' && (
            <p className="error">Not a valid SIN</p>
          )}
          <InputLabel htmlFor="sin" sx={{ color: 'black' }}>
            Social Insurance Number (SIN) (used for CRA income disclosure):
          </InputLabel>
          <Controller
            name="sin"
            control={control}
            render={({ field }) => (
              <TextField
                id="sin"
                inputProps={{ maxLength: 9 }}
                onChange={(e) => setValue('sin', e.target.value)}
              />
            )}
            rules={{
              validate: (inputtedSin) => {
                return isSINValid(inputtedSin);
              }
            }}
          />
        </FormGroup>
        <FormGroup sx={{ mt: '20px' }}>
          {errors?.drivers_licence?.type === 'dlFormat' && (
            <p className="error">Not a valid BC Driver's Licence Number</p>
          )}
          {errors?.drivers_licence?.type === 'backendAccessible' && (
            <p className="error">
              We cannot check your licence as your session may have expired;
              please log out and then log back in again.
            </p>
          )}
          {errors?.drivers_licence?.type === 'dlExists' && (
            <p className="error">
              This driver's licence number has already been submitted or issued
              a rebate.
            </p>
          )}
          <InputLabel htmlFor="drivers_licence" sx={{ color: 'black' }}>
            BC Driver's Licence number (You will present your licence at the new
            car dealership to redeem your rebate.
          </InputLabel>
          <InputLabel htmlFor="drivers_licence" sx={{ color: 'red' }}>
            Please ensure this number matches your licence otherwise you will
            not be able to claim your rebate
            <span style={{ color: 'black' }}>):</span>
          </InputLabel>
          <Controller
            name="drivers_licence"
            control={control}
            render={({ field }) => (
              <OutlinedInput
                id="drivers_licence"
                inputProps={{
                  maxLength: 8
                }}
                startAdornment={
                  <InputAdornment position="start">DL: </InputAdornment>
                }
                onChange={(e) => setValue('drivers_licence', e.target.value)}
              />
            )}
            rules={{
              validate: {
                dlFormat: (inputtedLicence) => {
                  if (
                    !inputtedLicence ||
                    (inputtedLicence.length !== 7 &&
                      inputtedLicence.length !== 8)
                  ) {
                    return false;
                  }
                  const regex = /^\d+$/;
                  if (!regex.test(inputtedLicence)) {
                    return false;
                  }
                  return true;
                },
                backendAccessible: async () => {
                  try {
                    setLoading(true);
                    await checkBackendAccessible();
                  } catch (error) {
                    return false;
                  }
                  return true;
                },
                dlExists: async (inputtedLicence) => {
                  try {
                    const response = await checkDLStatus(inputtedLicence);
                    if (response.data.drivers_license_valid === 'false') {
                      return false;
                    }
                  } catch (error) {
                    return false;
                  }
                  return true;
                }
              }
            }}
          />
        </FormGroup>
        {kcToken.identity_provider !== 'bcsc' && (
          <FormGroup sx={{ mt: '20px' }}>
            <Upload errors={errors} />
          </FormGroup>
        )}
        <FormGroup sx={{ mt: '20px' }}>
          <ConsentPersonal name="consent_personal" required={true} />
        </FormGroup>
        <FormGroup sx={{ mt: '20px' }}>
          <ConsentTax
            name="consent_tax"
            required={true}
            applicationType="individual"
          />
        </FormGroup>
        <Button
          variant="contained"
          type="submit"
          sx={{
            fontSize: '1.35rem',
            backgroundColor: '#003154',
            paddingX: '30px',
            paddingY: '10px'
          }}
          disabled={loading || bcscMissingFields.length > 0}
        >
          Submit Application
        </Button>
      </form>
    </FormProvider>
  );
};

export default Form;
