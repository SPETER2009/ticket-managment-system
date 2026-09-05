'use strict';
const { Model } = require('sequelize');
module.exports = (sequelize, DataTypes) => {
  class Priority extends Model {
    /**
     * Helper method for defining associations.
     * This method is not a part of Sequelize lifecycle.
     * The `models/index` file will call this method automatically.
     */
    static associate(models) {
      Priority.hasMany(models.Ticket, { foreignKey: 'priority_id' });
    }
  }
  Priority.init(
    {
      priority: DataTypes.STRING,
    },
    {
      sequelize,
      modelName: 'Priority',
    }
  );
  return Priority;
};
