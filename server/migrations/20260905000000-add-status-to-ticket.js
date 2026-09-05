'use strict';

module.exports = {
  up: async (queryInterface, Sequelize) => {
    await queryInterface.addColumn('Tickets', 'status', {
      type: Sequelize.STRING,
      allowNull: false,
      defaultValue: 'Open',
    });
  },

  down: async (queryInterface) => {
    await queryInterface.removeColumn('Tickets', 'status');
  },
};