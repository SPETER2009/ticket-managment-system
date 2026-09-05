import { Card, Tab, Tabs } from '@blueprintjs/core';
import { useState, useEffect, useContext, useCallback } from 'react';
import { UserContext } from './context/UserContext';
import Home from './components/Home';
import LoginForm from './components/Forms/LoginForm';
import RegisterForm from './components/Forms/RegisterForm';
import Axios from 'axios';
import { Switch, Route, Redirect } from 'react-router-dom';
import { Nav } from './components/Nav';

function App() {
  const [currentTab, setCurrentTab] = useState('login');
  const [userContext, setUserContext] = useContext(UserContext);

  const verifyUser = useCallback(async () => {
    try {
      const res = await Axios.post(
        '/refreshToken',
        {},
        {
          withCredentials: true,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (res.status === 200) {
        const data = res.data;
        setUserContext((oldValues) => {
          return { ...oldValues, token: data.token };
        });
      } else {
        setUserContext((oldValues) => {
          return { ...oldValues, token: null };
        });
      }
    } catch (error) {
      setUserContext((oldValues) => {
        return { ...oldValues, token: null };
      });
    }

    // call refreshToken every 5 minutes to renew the authentication token.
    setTimeout(verifyUser, 5 * 60 * 1000);
  }, [setUserContext]);

  useEffect(() => {
    verifyUser();
  }, [verifyUser]);

  const syncLogout = useCallback((event) => {
    if (event.key === 'logout') {
      window.location.reload();
    }
  }, []);

  useEffect(() => {
    window.addEventListener('storage', syncLogout);
    return () => {
      window.removeEventListener('storage', syncLogout);
    };
  }, [syncLogout]);

  if (userContext.token == null) {
    return (
      <>
        <Redirect
          to={{
            pathname: '/',
          }}
        />
        <Switch>
          <Route path='/'>
            <div className='login-background-gradient'></div>
            <Card elevation='1' className='centered'>
              <Tabs id='Tabs' onChange={setCurrentTab} selectedTabId={currentTab}>
                <Tab id='login' title='Login' panel={<LoginForm />} />
                <Tab id='register' title='Register' panel={<RegisterForm />} />
                <Tabs.Expander />
              </Tabs>
            </Card>
          </Route>
        </Switch>
      </>
    );
  }

  return (
    <>
      <Redirect
        to={{
          pathname: '/home',
        }}
      />
      <Nav />
      <Switch>
        <Route path='/home'>
          <Home refresh={verifyUser} />
        </Route>
      </Switch>
    </>
  );
}

export default App;
