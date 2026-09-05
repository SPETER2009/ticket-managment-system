import * as React from 'react';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { useState, useContext } from 'react';
import Axios from 'axios';
import { UserContext } from '../../context/UserContext';
import Alert from '@mui/material/Alert';
import Fade from '@material-ui/core/Fade';

const theme = createTheme();

function RegisterForm() {
  const [, setUserContext] = useContext(UserContext);
  const [userName, setUserName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userPassword, setUserPassword] = useState('');
  const [isValid, setIsValid] = useState(false);
  const [isInvalid, setIsInvalid] = useState(false);
  const [errMessage, setErrMessage] = useState('');

  const register = (event) => {
    event.preventDefault();
    Axios.post(
      '/register',
      { username: userName, email: userEmail, password: userPassword },
      {
        headers: {
          'Content-Type': 'application/json',
        },
        withCredentials: true,
      }
    )
      .then(async (res) => {
        setIsValid(true);
        setUserName('');
        setUserEmail('');
        setUserPassword('');
        setUserContext((oldValues) => {
          return { ...oldValues, token: res.data.token };
        });
      })
      .catch((err) => {
        let data = err.response.data;
        if (data.code) {
          setErrMessage(data.message);
          setIsInvalid(true);
        }
      });
  };

  return (
    <ThemeProvider theme={theme}>
      <Container component='main' maxWidth='xs'>
        <Fade in={isValid || isInvalid} timeout={1000}>
          <div>
            <div id='alert-succes-register' style={{ display: isValid ? 'inline' : 'none' }}>
              <Alert
                severity='success'
                variant='outlined'
                onClose={() => {
                  setIsValid(false);
                }}
                sx={{ margin: 0 }}>
                User registered Successfully
              </Alert>
            </div>
            <div id='alert-error-register' style={{ display: isInvalid ? 'inline' : 'none' }}>
              <Alert
                severity='error'
                variant='outlined'
                onClose={() => {
                  setIsInvalid(false);
                }}
                sx={{ margin: 0 }}>
                {errMessage}
              </Alert>
            </div>
          </div>
        </Fade>

        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}>
          <Avatar sx={{ m: 1, bgcolor: 'secondary.main' }}></Avatar>
          <Typography component='h1' variant='h5'>
            Sign up
          </Typography>
          <Box component='form' onSubmit={register} sx={{ mt: 3 }}>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField onChange={(event) => setUserName(event.target.value)} value={userName} required fullWidth label='Username' name='username' />
              </Grid>
              <Grid item xs={12}>
                <TextField onChange={(event) => setUserEmail(event.target.value)} value={userEmail} required fullWidth label='Email Address' type='email' name='email' autoComplete='email' />
              </Grid>
              <Grid item xs={12}>
                <TextField onChange={(event) => setUserPassword(event.target.value)} value={userPassword} required fullWidth name='password' label='Password' type='password' autoComplete='new-password' />
              </Grid>
            </Grid>
            <Button type='submit' fullWidth variant='contained' sx={{ mt: 3, mb: 2 }}>
              Sign Up
            </Button>
          
            
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default RegisterForm;
