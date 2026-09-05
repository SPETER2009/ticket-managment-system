import Axios from 'axios';
import React, { useContext } from 'react';
import { NavLink } from 'react-router-dom';
import { UserContext } from '../context/UserContext';

function Nav() {
  const [userContext, setUserContext] = useContext(UserContext);

  const logoutHandler = () => {
    Axios.get('/logout', {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${userContext.token}`,
      },
      withCredentials: true,
    }).then(async (res) => {
      setUserContext((oldValues) => {
        return { ...oldValues, details: undefined, token: null };
      });
      window.localStorage.setItem('logout', Date.now());
    });
  };
  return (
    <nav className='navbar navbar-expand navbar-dark bg-dark nav'>
      <div className='navbar-nav'>
        <NavLink exact to='/home' className='nav-item nav-link'>
          Home
        </NavLink>
        <NavLink exact to='/' className='nav-item nav-link' onClick={logoutHandler} style={{ 'marginLeft': 'auto' }}>
          Logout
        </NavLink>
      </div>
    </nav>
  );
}

export { Nav };
