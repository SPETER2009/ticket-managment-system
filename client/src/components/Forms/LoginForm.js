import * as React from 'react';
import Avatar from '@mui/material/Avatar';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import axios from 'axios';
import { useContext, useState } from 'react';
import { UserContext } from '../../context/UserContext';
import Alert from '@mui/material/Alert';
import Fade from '@material-ui/core/Fade';

const theme = createTheme();

function LoginForm(props) {
  const [userEmail, setUserEmail] = useState('');
  const [userPassword, setUserPassword] = useState('');
  const [, setUserContext] = useContext(UserContext);
  const [open, setOpen] = React.useState(false);

  const login = (event) => {
    event.preventDefault();

    axios
      .post(
        '/login',
        { email: userEmail, password: userPassword },
        {
          headers: {
            'Content-Type': 'application/json',
          },
          withCredentials: true,
        }
      )
      // , {withCredentials: true, credentials: 'include'})
      .then(async (res) => {
        setUserContext((oldValues) => {
          return { ...oldValues, token: res.data.token };
        });
      })
      .catch((err) => {
        setOpen(true);
      });
  };

  return (
    <ThemeProvider theme={theme}>
      <Container component='main' maxWidth='xs'>
        <Fade in={open} timeout={1000}>
          <div id='alert-error-login' style={{ display: open ? 'inline' : 'none' }}>
            <Alert severity='error' variant='outlined' sx={{ margin: 0 }}>
              Incorrect username or password
            </Alert>
          </div>
        </Fade>
        <CssBaseline />
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}>
          <Avatar sx={{ m: 1, bgcolor: 'secondary.main' }}></Avatar>
          <Typography component='h1' variant='h5'>
            Sign in
          </Typography>
          <Box component='form' onSubmit={login} sx={{ mt: 1 }}>
            <TextField margin='normal' onChange={(event) => setUserEmail(event.target.value)} value={userEmail} required fullWidth label='Email Address' type='email' name='email' autoComplete='email' />

            <TextField margin='normal' onChange={(event) => setUserPassword(event.target.value)} value={userPassword} required fullWidth name='password' label='Password' type='password' autoComplete='new-password' />

            <Button type='submit' fullWidth variant='contained' sx={{ mt: 3, mb: 2 }}>
              Sign in
            </Button>
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default LoginForm;
