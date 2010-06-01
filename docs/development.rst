Resources and Development
=========================

Mailing Lists
-------------

Supervisor has a maillist for users.  You may subscribe to the
`Supervisor-users maillist
<http://lists.supervisord.org/mailman/listinfo/supervisor-users>`_.

Supervisor has a maillist for checkins too.  You may subscribe to the
`Supervisor-checkins maillist
<http://lists.supervisord.org/mailman/listinfo/supervisor-checkins>`_.

Bug Tracker
-----------

Supervisor has a bugtracker where you may report any bugs or other
errors you find.  Please report bugs to the `collector
<http://www.plope.com/software/collector>`_.

Version Control Repository
--------------------------

You can also view the `Supervisor version control repository
<http://svn.supervisord.org>`_.

Contributing
------------

If you'd like to contribute to supervisor, please contact us through
the maillist and we'll attempt to arrange for you to have direct
access to the version control repository.  You may be required to sign
a contributor's agreement before you can be provided with access.

Sponsoring
----------

If you'd like to sponsor further Supervisor development (for custom
projects), please let one of the authors know.

Author Information
------------------

The following people are responsible for creating Supervisor.

Primary Authors and Maintainers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Chris McDonough (`Agendaless Consulting, Inc. <http://agendaless.com>`_)

- Mike Naberezny (`Maintainable Software, LLC. <http://maintainable.com>`_)

Contributors
~~~~~~~~~~~~

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
