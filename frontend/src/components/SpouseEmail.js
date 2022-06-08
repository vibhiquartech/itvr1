import React, { useEffect } from 'react';
import InputLabel from '@mui/material/InputLabel';
import TextField from '@mui/material/TextField';
import { FormGroup } from '@mui/material';
import { useFormContext } from 'react-hook-form';

const SpouseEmail = ({ name }) => {
  const {
    setValue,
    register,
    unregister,
    formState: { errors }
  } = useFormContext();

  useEffect(() => {
    register(name, { required: true });
    return () => {
      unregister(name);
    };
  }, [register, unregister]);

  return (
    <div>
      <FormGroup>
        {errors?.[name]?.type === 'required' && (
          <p className="error">Spouse email address cannot be blank</p>
        )}
        <p>enter your spouse or common law partner's email address</p>
        <InputLabel sx={{ color: 'black' }} htmlFor={name}>
          Spouse email address:
        </InputLabel>
        <TextField
          defaultValue=""
          type="text"
          name={name}
          onChange={(e) => setValue(name, e.target.value)}
        />
      </FormGroup>
    </div>
  );
};

export default SpouseEmail;
