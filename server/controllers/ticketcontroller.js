const Ticket = require('../models').Ticket;

exports.getTicket = (req, res) => {
  if (!req.body.id) {
    res.status(400).send({
      message: 'Content can not be empty!',
    });
  }
};

exports.createTicket = (req, res) => {
  if (!req.body.title || !req.body.description || !req.body.priority) {
    res.status(400).send({
      message: 'Content can not be empty!',
    });
    return;
  }
  const ticket = {
    title: req.body.title,
    user_id: req.user.id,
    description: req.body.description,
    priority_id: req.body.priority,
    status: req.body.status || 'Open',
  };
  Ticket.create(ticket)
    .then((createdTicket) => {
      res.status(201).send(createdTicket);
    })
    .catch((err) => {
      res.status(500).send({
        message: err.message || 'Some error occurred while creating the ticket.',
      });
    });
};

exports.updateTicket = (req, res) => {
  if (!req.body.title || !req.body.description || !req.body.priority || !req.body.status) {
    res.status(400).send({
      message: 'Content can not be empty!',
    });
    return;
  }
  const ticket = {
    id: req.body.id,
    title: req.body.title,
    description: req.body.description,
    priority_id: req.body.priority,
    status: req.body.status,
  };

  Ticket.update(
    { title: ticket.title, description: ticket.description, priority_id: ticket.priority_id, status: ticket.status },
    {
      where: {
        id: ticket.id,
      },
    }
  )
    .then(() => {
      res.send({ success: true });
    })
    .catch((err) => {
      res.status(500).send({
        message: err.message || 'Some error occurred while updating the ticket.',
      });
    });
};

exports.deleteTicket = (req, res) => {
  if (!req.body.id) {
    res.status(400).send({
      message: 'Content can not be empty!',
    });
    return;
  }
  const id = req.body.id;
  Ticket.destroy({
    where: {
      id: id,
    },
  })
    .then((ticket) => {
      res.send({ success: true });
    })
    .catch((err) => {
      res.status(500).send({
        message: err.message || 'Some error occurred while deleting the ticket.',
      });
    });
};
