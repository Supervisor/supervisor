Resources and Development
=========================

Mailing Lists
-------------

Supervisor has a mailing list for users.  You may subscribe to the
`Supervisor-users mailing list
<http://lists.supervisord.org/mailman/listinfo/supervisor-users>`_.

Supervisor has a mailing list for checkins too.  You may subscribe to the
`Supervisor-checkins mailing list
<http://lists.supervisord.org/mailman/listinfo/supervisor-checkins>`_.

Bug Tracker
-----------

Supervisor has a bugtracker where you may report any bugs or other
errors you find.  Please report bugs to the `GitHub issues page
<https://github.com/supervisor/supervisor/issues>`_.

Version Control Repository
--------------------------

You can also view the `Supervisor version control repository
<https://github.com/Supervisor/supervisor>`_.

Contributing
------------

Supervisor development is discussed on the mailing list.  We'll review
contributions from the community in both
`pull requests <https://help.github.com/articles/using-pull-requests>`_
on GitHub (preferred) and patches sent to the list.

Author Information
------------------

The following people are responsible for creating Supervisor.

Original Author
~~~~~~~~~~~~~~~

- `Chris McDonough <http://plope.com>`_ is the original author of Supervisor.

Contributors
~~~~~~~~~~~~

Contributors are tracked on the `GitHub contributions page
<https://github.com/Supervisor/supervisor/graphs/contributors>`_.

The list below recognizes significant contributions that were made before
the repository moved to GitHub.

- Anders Quist: Anders contributed the patch that was the basis for
  Supervisor’s ability to reload parts of its configuration without
  restarting.

- Derek DeVries: Derek did the web design of Supervisor’s internal web
  interface and website logos.

- Guido van Rossum: Guido authored ``zdrun`` and ``zdctl``, the
  programs from Zope that were the original basis for Supervisor.  He
  also created Python, the programming language that Supervisor is
  written in.

- Jason Kirtland: Jason fixed Supervisor to run on Python 2.6 by
  contributing a patched version of Medusa (a Supervisor dependency)
  that we now bundle.

- Roger Hoover: Roger added support for spawning FastCGI programs. He
  has also been one of the most active mailing list users, providing
  his testing and feedback.

- Siddhant Goel: Siddhant worked on :program:`supervisorctl` as our
  Google Summer of Code student for 2008. He implemented the ``fg``
  command and also added tab completion.
