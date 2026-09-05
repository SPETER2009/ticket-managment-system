import Axios from 'axios';
import { useState, useContext, useCallback, useEffect } from 'react';
import Popup from './Popup';
import TicketForm from './Forms/TicketForm';
import { UserContext } from '../context/UserContext';
import Loader from '../Loader';
import { Button } from '@blueprintjs/core';

function Home(props) {
  const [userContext, setUserContext] = useContext(UserContext);
  const [openPopup, setOpenPopup] = useState(false);
  const [ticketForEdit, setTicketForEdit] = useState(null);
  const [tickets, setTickets] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  const filteredTickets = tickets
    ? tickets.filter((ticket) => {
        const search = searchTerm.toLowerCase();
        const matchesSearch = ticket.title.toLowerCase().includes(search) || ticket.description.toLowerCase().includes(search);
        const matchesPriority = priorityFilter === 'all' || String(ticket.Priority.id) === priorityFilter;
        const matchesStatus = statusFilter === 'all' || ticket.status === statusFilter;
        return matchesSearch && matchesPriority && matchesStatus;
      })
    : null;

  const fetchUserDetails = useCallback(() => {
    Axios.get('/me', {
      withCredentials: true,
      // Pass authentication token as bearer token in header
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${userContext.token}`,
      },
    }).then(async (response) => {
      if (response.status === 200) {
        const data = response.data;
        setUserContext((oldValues) => {
          return { ...oldValues, details: data };
        });
      } else {
        if (response.status === 401) {
          // Edge case: when the token has expired.
          // This could happen if the refreshToken calls have failed due to network error or
          // User has had the tab open from previous day and tries to click on the Fetch button
          window.location.reload();
        } else {
          setUserContext((oldValues) => {
            return { ...oldValues, details: null };
          });
        }
      }
    }).catch(() => {
      setUserContext((oldValues) => {
        return { ...oldValues, details: null };
      });
    });
  }, [setUserContext, userContext.token]);

  const fetchTickets = useCallback(() => {
    return Axios.get('/user/tickets', {
      withCredentials: true,
      // Pass authentication token as bearer token in header
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${userContext.token}`,
      },
    }).then(async (response) => {
      if (response.status === 200) {
        const data = response.data;
        data.sort((a, b) => {
          if (a.id < b.id) {
            return -1;
          }
          if (a.id > b.id) {
            return 1;
          }
          return 0;
        });
        setTickets(data);
      } else {
        if (response.status === 401) {
          window.location.reload();
        } else {
          setUserContext((oldValues) => {
            return { ...oldValues, details: null };
          });
        }
      }
    });
  }, [setUserContext, userContext.token]);

  const createTicket = (ticket) => {
    return Axios.post(
      '/ticket',
      { title: ticket.title, description: ticket.description, priority: ticket.priority, status: ticket.status },
      {
        withCredentials: true,
        // Pass authentication token as bearer token in header
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userContext.token}`,
        },
      }
    ).catch((err) => {
      console.log(err);
    });
  };
  const updateTicket = (ticket) => {
    return Axios.put(
      '/ticket',
      { id: ticket.id, title: ticket.title, description: ticket.description, priority: ticket.priority, status: ticket.status },
      {
        withCredentials: true,
        // Pass authentication token as bearer token in header
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userContext.token}`,
        },
      }
    ).catch((err) => {
      console.log(err);
    });
  };

  //Finish add, remove, update tickets
  const deleteTicket = (ticket_id) => {
    setDeleting(true);
    Axios.post(
      '/ticket/delete',
      { id: ticket_id },
      {
        withCredentials: true,
        // Pass authentication token as bearer token in header
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userContext.token}`,
        },
      }
    )
      .then((res) => {
        setDeleting(false);
        fetchTickets();
      })
      .catch((err) => {
        console.log(err);
      });
  };

  const addOrEdit = async (ticket) => {
    if (ticket.id === 0) {
      await createTicket(ticket);
    } else {
      await updateTicket(ticket);
    }
    setTicketForEdit(null);
    setOpenPopup(false);
    fetchTickets();
  };

  useEffect(() => {
    // fetch only when user details are not present
    if (!userContext.details) {
      fetchUserDetails();
    }
  }, [userContext.details, fetchUserDetails]);

  useEffect(() => {
    if (userContext.details && !tickets) {
      fetchTickets();
    }
  }, [userContext.details, tickets, fetchTickets]);

  return userContext.details === null ? (
    'Error Loading User details'
  ) : !userContext.details ? (
    <Loader />
  ) : (
    <>
      <div className='centered-form'>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <h1 style={{ fontSize: '40px' }}>Tickets</h1>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '10px' }}>
          <input
            className='form-control'
            placeholder='Search tickets'
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            style={{ flex: '1 1 220px' }}
          />
          <select className='form-select' value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} style={{ flex: '0 1 150px' }}>
            <option value='all'>All priorities</option>
            <option value='1'>Low</option>
            <option value='2'>Normal</option>
            <option value='3'>Medium</option>
            <option value='4'>High</option>
          </select>
          <select className='form-select' value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} style={{ flex: '0 1 160px' }}>
            <option value='all'>All statuses</option>
            <option value='Open'>Open</option>
            <option value='In Progress'>In Progress</option>
            <option value='Resolved'>Resolved</option>
            <option value='Closed'>Closed</option>
          </select>
        </div>
        <Button
          intent='success'
          className='btn btn-sm btn-success mb-2'
          style={{ float: 'right' }}
          onClick={() => {
            setOpenPopup(true);
            setTicketForEdit(null);
          }}>
          Add Ticket
        </Button>
        <div className='table-wrapper-scroll-y my-custom-scrollbar'>
          <table className='table table-striped'>
            <thead>
              <tr>
                <th style={{ width: '30%' }}>Title</th>
                <th style={{ width: '30%' }}>Description</th>
                <th style={{ width: '30%' }}>Priority</th>
                <th style={{ width: '15%' }}>Status</th>
                <th style={{ width: '10%' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredTickets &&
                filteredTickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td>{ticket.title}</td>
                    <td>{ticket.description}</td>
                    <td>{ticket.Priority.priority}</td>
                    <td>{ticket.status || 'Open'}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <Button
                        className='btn btn-sm btn-primary mr-1'
                        onClick={() => {
                          setOpenPopup(true);
                          setTicketForEdit(ticket);
                        }}>
                        Edit
                      </Button>
                      <Button
                        onClick={() => {
                          if (window.confirm('Are you sure you wish to delete this ticket?')) deleteTicket(ticket.id);
                        }}
                        className='btn btn-sm btn-danger'
                        disabled={deleting}>
                        {deleting ? <span className='spinner-border spinner-border-sm'></span> : <span>Delete</span>}
                      </Button>
                    </td>
                  </tr>
                ))}
              {!tickets && (
                <tr>
                  <td colSpan='5' className='text-center'>
                    <div className='spinner-border spinner-border-lg align-center'></div>
                  </td>
                </tr>
              )}
              {tickets && !filteredTickets.length && (
                <tr>
                  <td colSpan='5' className='text-center'>
                    <div className='p-2'>No matching tickets</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <Popup title='Ticket Form' openPopup={openPopup} setOpenPopup={setOpenPopup}>
        <TicketForm ticketForEdit={ticketForEdit} addOrEdit={addOrEdit} />
      </Popup>
    </>
  );
}

export default Home;
