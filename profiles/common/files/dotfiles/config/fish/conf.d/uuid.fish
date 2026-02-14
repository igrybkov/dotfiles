if type -q uuidgen && not type -q uuid
  abbr --add -g uuid 'uuidgen | string lower'
  abbr --add -g uuidgen 'uuidgen | string lower'
end
