import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import TextField from '@mui/material/TextField';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import InputLabel from '@mui/material/InputLabel';
import { useEffect, useState } from 'react';
import NativeSelect from '@mui/material/NativeSelect';

const theme = createTheme();

function TicketForm({addOrEdit, ticketForEdit}) {
  const [id, setId] = useState(0);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(1);
  const [status, setStatus] = useState('Open');
  const [titleError, setTitleError] = useState(false);
  const [descriptionError, setDescriptionError] = useState(false);


  const SubmitTicket = () => {
    if (titleError || descriptionError) {
    } else {
      const values = {
        id: id,
        title: title,
        description: description,
        priority: priority,
        status: status,
      };
      addOrEdit(values);
    }
  };

  useEffect(() => {
    if (ticketForEdit != null) {
      setId(ticketForEdit.id);
      setTitle(ticketForEdit.title);
      setDescription(ticketForEdit.description);
      setPriority(ticketForEdit.Priority.id);
      setStatus(ticketForEdit.status || 'Open');
    } else {
      setId(0);
      setTitle('');
      setDescription('');
      setPriority(1);
      setStatus('Open');
    }
  }, [ticketForEdit]);

  useEffect(() => {
    if (title === '') {
      setTitleError(true);
    } else {
      setTitleError(false);
    }
  }, [title, setTitle]);

  useEffect(() => {
    if (description === '') {
      setDescriptionError(true);
    } else {
      setDescriptionError(false);
    }
  }, [description, setDescription]);

  return (
    <ThemeProvider theme={theme}>
      <Container component='main' maxWidth='xs'>
        <CssBaseline />
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}>
          <Box component='form'>
            <TextField
              margin='normal'
              required
              fullWidth
              id='title'
              label='Title'
              name='title'
              autoFocus
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
              }}
              error={titleError}
            />
            <TextField
              margin='normal'
              required
              fullWidth
              name='description'
              label='Description'
              id='description'
              multiline
              rows={4}
              value={description}
              onChange={(e) => {
                setDescription(e.target.value);
              }}
              error={descriptionError}
            />
            <InputLabel id='priority-label'>Priority</InputLabel>
            <NativeSelect
              required
              labelId='priority-label'
              id='priority'
              value={priority}
              label='Priority'
              autoWidth
              onChange={(e) => {
                setPriority(e.target.value);
              }}>
              <option value={1}>Low</option>
              <option value={2}>Normal</option>
              <option value={3}>Medium</option>
              <option value={4}>High</option>
            </NativeSelect>
            <InputLabel id='status-label' style={{ marginTop: '16px' }}>Status</InputLabel>
            <NativeSelect
              required
              labelId='status-label'
              id='status'
              value={status}
              label='Status'
              autoWidth
              onChange={(e) => {
                setStatus(e.target.value);
              }}>
              <option value='Open'>Open</option>
              <option value='In Progress'>In Progress</option>
              <option value='Resolved'>Resolved</option>
              <option value='Closed'>Closed</option>
            </NativeSelect>
            <Button fullWidth variant='contained' style={{ marginTop: '10%' }} onClick={SubmitTicket}>
              Submit
            </Button>
          </Box>
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default TicketForm;
