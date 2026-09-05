'use strict';
const { Query } = require('pg');
const User = require('../models').User;
const Ticket = require('../models').Ticket;
const Priority = require('../models').Priority;
module.exports = {
  up: async (queryInterface, Sequelize) => {
    await User.bulkCreate([
      {
        username: 'Demetrio',
        password: '12345',
        email: 'demetrioq@gmail.com',
      },
      {
        username: 'Usuario2',
        password: 'user2pass',
        email: 'user2@gmail.com',
      },
      {
        username: 'Usuario3',
        password: 'user3pass',
        email: 'user3@gmail.com',
      },
      {
        username: 'Usuario4',
        password: 'user4pass',
        email: 'user4@gmail.com',
      },
      {
        username: 'Usuario5',
        password: 'user5pass',
        email: 'user5@gmail.com',
      },
    ]);

    await Priority.bulkCreate([
      {
        id: 1,
        priority: 'low',
      },
      {
        id: 2,
        priority: 'normal',
      },
      {
        id: 3,
        priority: 'medium',
      },
      {
        id: 4,
        priority: 'high',
      },
    ]);

    const users = await queryInterface.sequelize.query('Select id from public."Users";');

    const userRows = users[0];
    return Ticket.bulkCreate([
      {
        user_id: userRows[0].id,
        priority_id: 1,
        title: 'Ticket 1',
        description: 'problem x with y',
      },
      {
        user_id: userRows[0].id,
        priority_id: 2,
        title: 'Ticket 2',
        description: 'Another Problem',
      },
      {
        user_id: userRows[0].id,
        priority_id: 3,
        title: 'Ticket 3',
        description: 'Dk what this is',
      },
      {
        user_id: userRows[0].id,
        priority_id: 4,
        title: 'Ticket 4',
        description: 'Ticket 4 description',
      },
    ]);
  },

  down: async (queryInterface, Sequelize) => {
    await queryInterface.bulkDelete('Tickets', null, {});
    await queryInterface.bulkDelete('Priorities', null, {});
    return queryInterface.bulkDelete('Users', null, {});
  },
};
